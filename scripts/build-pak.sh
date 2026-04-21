#!/bin/bash
# ============================================================================
# Azure Management Pack — Build & Patch Script
#
# Wraps mp-build to:
# 1. Run mp-build as normal
# 2. Patch the generated describe.xml with UI integration attributes
#    (type, subType, worldObjectName, PowerState, showTag)
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
ADAPTER_KIND=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["adapter_kinds"][0])' "${ADAPTER_DIR}/manifest.txt")

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sign) SIGN=true; shift ;;
        --test) TEST_ONLY=true; shift ;;
        --registry) REGISTRY_TAG="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$ADAPTER_DIR"

if $TEST_ONLY; then
    echo "=== Running mp-test ==="
    sudo mp-test --port "$PORT"
    exit 0
fi

echo "=== Step 1: Building pak with mp-build ==="
sudo mp-build -i --no-ttl --registry-tag "$REGISTRY_TAG" -P "$PORT"

echo ""
echo "=== Step 2: Patching describe.xml ==="
# Find the generated describe.xml
if [ -f conf/describe.xml ]; then
    python3 "$SCRIPT_DIR/patch-describe-xml.py" conf/describe.xml
else
    echo "WARNING: conf/describe.xml not found — skipping patch"
    echo "The describe.xml may be inside the built .pak file."
    echo "Attempting to patch inside the .pak..."

    PAK_FILE=$(ls -t build/*.pak 2>/dev/null | head -1)
    if [ -n "$PAK_FILE" ]; then
        TEMP_DIR=$(mktemp -d)
        trap "rm -rf $TEMP_DIR" EXIT

        # Extract, patch, repack
        unzip -q "$PAK_FILE" -d "$TEMP_DIR/pak"

        # Find describe.xml inside adapter.zip
        if [ -f "$TEMP_DIR/pak/adapter.zip" ]; then
            mkdir -p "$TEMP_DIR/adapter"
            unzip -q "$TEMP_DIR/pak/adapter.zip" -d "$TEMP_DIR/adapter"

            DESCRIBE="$TEMP_DIR/adapter/$ADAPTER_KIND/conf/describe.xml"
            if [ -f "$DESCRIBE" ]; then
                python3 "$SCRIPT_DIR/patch-describe-xml.py" "$DESCRIBE"

                # Repack adapter.zip
                cd "$TEMP_DIR/adapter"
                zip -r -q "$TEMP_DIR/pak/adapter.zip" .
                cd "$ADAPTER_DIR"
            fi
        fi

        # Repack .pak
        cd "$TEMP_DIR/pak"
        zip -r -q "$PAK_FILE" .
        cd "$ADAPTER_DIR"
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
