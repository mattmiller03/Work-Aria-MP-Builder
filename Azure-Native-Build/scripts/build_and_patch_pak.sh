#!/usr/bin/env bash
# Build the Azure pak with dashboard.json patched to use our pak's
# resourceKind ids. See scripts/patch_dashboard_kind_ids.py for the
# why -- short version: native dashboards reference kinds by numeric
# id (resourceKind:id:N), those positions are pak-specific, and
# imported as-is the dashboards bind tiles to the wrong kinds.
#
# Workflow:
#   1. Build the pak once -> produces describe.xml inside the pak.
#   2. Extract describe.xml.
#   3. Run the Python patcher to rewrite resourceKind:id:N references
#      in content/dashboards/azure/dashboard.json.
#   4. Rebuild the pak so the patched dashboard ships inside it.
#
# Usage:
#   ./scripts/build_and_patch_pak.sh <registry-ip>
# Example:
#   ./scripts/build_and_patch_pak.sh 10.1.2.3

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <registry-ip>" >&2
    echo "Example: $0 10.1.2.3" >&2
    exit 2
fi

REGISTRY_IP="$1"
REGISTRY_PORT="${REGISTRY_PORT:-5000}"
REGISTRY_IMAGE="${REGISTRY_IMAGE:-azuregovcloud-adapter}"
ADAPTER_PORT="${ADAPTER_PORT:-8181}"

# Resolve script + repo root regardless of where you invoke from.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd)"
DASHBOARD_JSON="$REPO_ROOT/content/dashboards/azure/dashboard.json"
PATCHER="$SCRIPT_DIR/patch_dashboard_kind_ids.py"
BUILD_DIR="$REPO_ROOT/build"

if [[ ! -f "$DASHBOARD_JSON" ]]; then
    echo "ERROR: dashboard.json not found at $DASHBOARD_JSON" >&2
    exit 1
fi
if [[ ! -f "$PATCHER" ]]; then
    echo "ERROR: patcher script not found at $PATCHER" >&2
    exit 1
fi

REGISTRY_TAG="${REGISTRY_IP}:${REGISTRY_PORT}/${REGISTRY_IMAGE}"
TMPDIR="$(mktemp -d -t azpak-patch-XXXXXX)"
trap 'rm -rf "$TMPDIR"' EXIT

echo "==> Registry tag: $REGISTRY_TAG"
echo "==> Repo root:    $REPO_ROOT"
echo "==> Temp dir:     $TMPDIR"
echo

# Run mp-build from inside the repo root so it picks up manifest.txt etc.
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Step 1: First build -> produces describe.xml inside the pak
# ---------------------------------------------------------------------------
echo "==> [1/4] First mp-build (to extract post-loader describe.xml)"
sudo mp-build -i --no-ttl --registry-tag "$REGISTRY_TAG" -P "$ADAPTER_PORT"

# Find the freshest pak in build/. mp-build embeds the version in the name
# (MicrosoftAzureAdapter_<version>.pak); pick whatever it just wrote.
shopt -s nullglob
PAKS=("$BUILD_DIR"/MicrosoftAzureAdapter_*.pak)
shopt -u nullglob
if [[ ${#PAKS[@]} -eq 0 ]]; then
    echo "ERROR: No MicrosoftAzureAdapter_*.pak in $BUILD_DIR after mp-build" >&2
    exit 1
fi
# Newest-first (mp-build is sequential so latest mtime is the pak we just built).
LATEST_PAK="$(ls -t "${PAKS[@]}" | head -n 1)"
echo "    Built pak: $LATEST_PAK"

# ---------------------------------------------------------------------------
# Step 2: Extract describe.xml from inside the pak.
# It may live at any depth (typically conf/describe.xml) and may be
# bundled directly inside the pak OR nested inside an adapter.zip --
# match the layout-agnostic search done by scripts/verify_collection.py.
# ---------------------------------------------------------------------------
echo
echo "==> [2/4] Extracting describe.xml from $LATEST_PAK"

# Try the outer pak first.
DIRECT_PATH="$(unzip -Z1 "$LATEST_PAK" | grep -E '(^|/)describe\.xml$' | head -n 1 || true)"
if [[ -n "$DIRECT_PATH" ]]; then
    echo "    Found at $DIRECT_PATH (in pak)"
    unzip -p "$LATEST_PAK" "$DIRECT_PATH" > "$TMPDIR/describe.xml"
else
    # Fall back to scanning each adapter.zip for a nested describe.xml.
    NESTED_ZIP="$(unzip -Z1 "$LATEST_PAK" | grep -E '(^|/)adapter\.zip$' | head -n 1 || true)"
    if [[ -z "$NESTED_ZIP" ]]; then
        echo "ERROR: pak has neither a describe.xml nor an adapter.zip" >&2
        exit 1
    fi
    echo "    Pak has no top-level describe.xml -- looking inside $NESTED_ZIP"
    unzip -p "$LATEST_PAK" "$NESTED_ZIP" > "$TMPDIR/adapter.zip"
    INNER_PATH="$(unzip -Z1 "$TMPDIR/adapter.zip" | grep -E '(^|/)describe\.xml$' | head -n 1 || true)"
    if [[ -z "$INNER_PATH" ]]; then
        echo "ERROR: adapter.zip has no describe.xml entry" >&2
        echo "       (entries: $(unzip -Z1 "$TMPDIR/adapter.zip" | head -n 20))" >&2
        exit 1
    fi
    echo "    Found at $INNER_PATH (in adapter.zip)"
    unzip -p "$TMPDIR/adapter.zip" "$INNER_PATH" > "$TMPDIR/describe.xml"
fi

if [[ ! -s "$TMPDIR/describe.xml" ]]; then
    echo "ERROR: describe.xml extracted empty -- pak layout may have changed" >&2
    exit 1
fi
echo "    Extracted: $TMPDIR/describe.xml ($(wc -c < "$TMPDIR/describe.xml") bytes)"

# ---------------------------------------------------------------------------
# Step 3: Patch dashboard.json in place
# ---------------------------------------------------------------------------
echo
echo "==> [3/4] Patching dashboard.json resourceKind:id:N references"
python3 "$PATCHER" \
    --describe "$TMPDIR/describe.xml" \
    --dashboard "$DASHBOARD_JSON"

# ---------------------------------------------------------------------------
# Step 4: Rebuild the pak so the patched dashboard ships inside it
# ---------------------------------------------------------------------------
echo
echo "==> [4/4] Second mp-build (packaging patched dashboard.json)"
sudo mp-build -i --no-ttl --registry-tag "$REGISTRY_TAG" -P "$ADAPTER_PORT"

# Re-find the latest pak in case the version got bumped between builds.
shopt -s nullglob
PAKS=("$BUILD_DIR"/MicrosoftAzureAdapter_*.pak)
shopt -u nullglob
FINAL_PAK="$(ls -t "${PAKS[@]}" | head -n 1)"
echo
echo "==> Done. Patched pak: $FINAL_PAK"
echo "    Push to registry with:"
echo "      sudo docker tag azuregovcloud-test:<VERSION> ${REGISTRY_TAG}:latest"
echo "      sudo docker push ${REGISTRY_TAG}:latest"
