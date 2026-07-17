#!/bin/bash
# ============================================================================
# Azure Management Pack — Build & Patch Script
#
# Wraps mp-build to:
# 1. Run mp-build as normal
# 2. Run the describe.xml pipeline on the generated pak:
#      a. patch-describe-xml.py    — native-kind substitution + UI attributes
#                                    (type, subType, worldObjectName,
#                                    PowerState, showTag, SERVICES/REGIONS)
#      b. merge-custom-attrs.py    — graft SDK-defined custom attrs (flat and
#                                    grouped) that native substitution drops;
#                                    fixes the ~87K "not defined in
#                                    describe.xml" warnings
#      c. fix-namekeys.py          — remap kind nameKeys that collide with the
#                                    SDK resources dictionary (label impostors
#                                    like AZURE_STORAGE_DISK -> "Network In")
#      d. cleanup-describe-xml.py  — strip constructs the SDK schema rejects
#                                    (enumUnselected, advanced, empty length,
#                                    dup attrs, dispOrder collisions) and
#                                    VALIDATE against the pak's own XSD.
#                                    Build ABORTS on validation failure —
#                                    this gate is what prevents another
#                                    silent APPLY_ADAPTER reject.
# 3. Optionally sign the .pak with a custom certificate
#
# Usage:
#   ./build-pak.sh                    # Build only
#   ./build-pak.sh --sign             # Build + sign
#   ./build-pak.sh --test             # Test only (mp-test)
#
# Run from the adapter directory (Azure-Native-Build/)
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REGISTRY_TAG="${REGISTRY_TAG:-214.73.76.134:5000/azuregovcloud-adapter}"
PORT="${PORT:-8181}"
SIGN=false
TEST_ONLY=false
NO_PATCH=false

# Where the pre-patch SDK describe.xml snapshot is saved for merge-custom-attrs
DEBUG_DIR="/opt/aria/Aria-MP-Builder/debug"
SDK_SNAPSHOT="$DEBUG_DIR/describe-sdk-prepatch.xml"

# --- Self-logging ----------------------------------------------------------
# Mirror ALL script output to $DEBUG_DIR/build.log at an ABSOLUTE path, so
# the log lands in the same place regardless of the directory the script is
# launched from (repo root vs Azure-Native-Build/ — a relative
# `| tee debug/build.log` writes to whichever debug/ is under the CWD).
# An outer `... 2>&1 | tee debug/build.log` is no longer needed, but harmless.
BUILD_LOG="$DEBUG_DIR/build.log"
mkdir -p "$DEBUG_DIR"
exec > >(tee "$BUILD_LOG") 2>&1
echo "=== build-pak.sh run started $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "=== log: $BUILD_LOG ==="

# Pin the host-side Python to the 3.12 we installed at /opt/python312
# (Photon's default python3 is 3.10/3.11, which may not match the SDK).
# Override with PYTHON_BIN=/some/python if needed.
if [[ -n "${PYTHON_BIN:-}" ]]; then
    :
elif command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.12)"
else
    PYTHON_BIN="$(command -v python3)"
fi
echo "Using python: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"

# Resolve ADAPTER_DIR. Honor an explicit override, else try the two known layouts
# (repo-native Azure-Native-Build/, or the renamed Azure/ that servers sometimes use).
if [[ -n "${ADAPTER_DIR:-}" ]]; then
    :
elif [[ -f "${SCRIPT_DIR}/../Azure-Native-Build/manifest.txt" ]]; then
    ADAPTER_DIR="${SCRIPT_DIR}/../Azure-Native-Build"
elif [[ -f "${SCRIPT_DIR}/../Azure/manifest.txt" ]]; then
    ADAPTER_DIR="${SCRIPT_DIR}/../Azure"
else
    echo "ERROR: Could not find adapter directory. Expected one of:"
    echo "  ${SCRIPT_DIR}/../Azure-Native-Build/manifest.txt"
    echo "  ${SCRIPT_DIR}/../Azure/manifest.txt"
    echo "Or set ADAPTER_DIR=/path/to/adapter before running."
    exit 1
fi
echo "Using adapter directory: $ADAPTER_DIR"

# Read adapter kind from manifest.txt so path lookups stay in sync with pak name.
ADAPTER_KIND=$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["adapter_kinds"][0])' "${ADAPTER_DIR}/manifest.txt")

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sign) SIGN=true; shift ;;
        --test) TEST_ONLY=true; shift ;;
        --no-patch) NO_PATCH=true; shift ;;
        --registry) REGISTRY_TAG="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$ADAPTER_DIR"
mkdir -p "$DEBUG_DIR"

# Unified cleanup run on EXIT (success or failure). Two responsibilities:
#
# 1. Reap zombie adapter containers from prior failed mp-build / mp-test
#    runs. Each crash leaves a container running `python3 -m swagger_server`
#    whose /tmp lives in host overlay storage and accumulates over time —
#    eventually filling /tmp and causing `tempfile.mkdtemp() OSError 28`
#    inside swagger_server, which surfaces as `/adapterDefinition` 500.
# 2. Remove the patch-step's mktemp -d directory if one was created.
#
# Filtered strictly by image ancestor `microsoftazureadapter-test` so the
# long-running mp-builder-app and registry containers are never touched.
# Idempotent: silent no-op if there are no matching resources.
TEMP_DIR=""
cleanup_all() {
    local ids
    ids=$(sudo docker ps -aq --filter "ancestor=microsoftazureadapter-test" 2>/dev/null || true)
    if [[ -n "$ids" ]]; then
        echo "Reaping $(echo "$ids" | wc -l) leftover microsoftazureadapter-test container(s)..."
        echo "$ids" | xargs -r sudo docker rm -f >/dev/null 2>&1 || true
    fi
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup_all EXIT

# Reap any zombies left over from prior runs before we build a new image.
cleanup_all

if $TEST_ONLY; then
    echo "=== Running mp-test ==="
    sudo mp-test --port "$PORT"
    exit 0
fi

echo "=== Step 1: Building pak with mp-build ==="
sudo mp-build -i --no-ttl --registry-tag "$REGISTRY_TAG" -P "$PORT"

echo ""
echo "=== Step 2: describe.xml pipeline (patch -> merge -> namekeys -> cleanup+validate) ==="
if $NO_PATCH; then
    echo "Skipped (--no-patch). Pak will ship with pure SDK-generated describe.xml."
# mp-build generates describe.xml inside adapter.zip inside the .pak, not on
# disk at conf/describe.xml, so the expected path is the "else" fallback below.
elif [ -f conf/describe.xml ]; then
    cp conf/describe.xml "$SDK_SNAPSHOT"
    "$PYTHON_BIN" "$SCRIPT_DIR/patch-describe-xml.py" conf/describe.xml
    "$PYTHON_BIN" "$SCRIPT_DIR/merge-custom-attrs.py" conf/describe.xml "$SDK_SNAPSHOT"
    "$PYTHON_BIN" "$SCRIPT_DIR/fix-namekeys.py" conf/describe.xml
    "$PYTHON_BIN" "$SCRIPT_DIR/cleanup-describe-xml.py" conf/describe.xml --validate || {
        echo "FATAL: describe.xml failed schema validation after cleanup — aborting build"
        exit 1
    }
else
    echo "Patching describe.xml inside the built .pak..."

    PAK_FILE=$(ls -t build/*.pak 2>/dev/null | head -1)
    if [ -n "$PAK_FILE" ]; then
        # Absolute path so later cd commands don't break zip's output target.
        PAK_FILE="$(readlink -f "$PAK_FILE")"

        TEMP_DIR=$(mktemp -d)
        # cleanup_all (registered above) will rm -rf $TEMP_DIR on exit.

        # Extract, patch, repack
        unzip -q "$PAK_FILE" -d "$TEMP_DIR/pak"

        # Find describe.xml inside adapter.zip
        if [ -f "$TEMP_DIR/pak/adapter.zip" ]; then
            mkdir -p "$TEMP_DIR/adapter"
            unzip -q "$TEMP_DIR/pak/adapter.zip" -d "$TEMP_DIR/adapter"

            DESCRIBE="$TEMP_DIR/adapter/$ADAPTER_KIND/conf/describe.xml"
            if [ -f "$DESCRIBE" ]; then
                # --- Stage 0: snapshot the raw SDK-emitted describe.xml
                #     (input for merge-custom-attrs below)
                cp "$DESCRIBE" "$SDK_SNAPSHOT"

                # --- Stage 1: native-kind substitution + UI attribute patches
                "$PYTHON_BIN" "$SCRIPT_DIR/patch-describe-xml.py" "$DESCRIBE"

                # --- Stage 2: graft SDK-defined grouped/flat custom attrs
                #     lost in native substitution (fixes the ~87K "not
                #     defined in describe.xml" warnings — Defect A)
                "$PYTHON_BIN" "$SCRIPT_DIR/merge-custom-attrs.py" "$DESCRIBE" "$SDK_SNAPSHOT"

                # --- Stage 3: fix kind display names (native nameKeys
                #     collide with the SDK resources dictionary — the
                #     "Network In" / "Tenant ID" label impostors)
                "$PYTHON_BIN" "$SCRIPT_DIR/fix-namekeys.py" "$DESCRIBE"

                # --- Stage 4: final sanitization + schema self-check
                #     (fixes that unblocked APPLY_ADAPTER on 2026-07-08).
                #     HARD GATE: build aborts on any validation error.
                "$PYTHON_BIN" "$SCRIPT_DIR/cleanup-describe-xml.py" "$DESCRIBE" --validate || {
                    echo "FATAL: describe.xml failed schema validation after cleanup — aborting build"
                    exit 1
                }

                # Repack adapter.zip (remove old archive so zip doesn't just update it)
                rm -f "$TEMP_DIR/pak/adapter.zip"
                (cd "$TEMP_DIR/adapter" && zip -r -q "$TEMP_DIR/pak/adapter.zip" .)
            else
                echo "ERROR: describe.xml not found at $DESCRIBE"
                echo "Contents of $TEMP_DIR/adapter:"
                ls -la "$TEMP_DIR/adapter"
                exit 1
            fi
        fi

        # Repack .pak (overwrite the mp-build output with patched content)
        rm -f "$PAK_FILE"
        (cd "$TEMP_DIR/pak" && zip -r -q "$PAK_FILE" .)
        echo "Patched .pak file: $PAK_FILE"
    fi
fi

if $SIGN; then
    echo ""
    echo "=== Step 3: Signing pak ==="
    PAK_FILE=$(ls -t build/*.pak 2>/dev/null | head -1)
    if [ -n "$PAK_FILE" ]; then
        bash "$SCRIPT_DIR/sign-pak.sh" "$PAK_FILE"
    else
        echo "WARNING: No .pak file found to sign"
    fi
fi

echo ""
echo "=== Build complete ==="
PAK_FILE=$(ls -t build/*.pak 2>/dev/null | head -1)
if [ -n "$PAK_FILE" ]; then
    echo "Pak file: $PAK_FILE"
    echo "Size: $(du -h "$PAK_FILE" | awk '{print $1}')"
fi