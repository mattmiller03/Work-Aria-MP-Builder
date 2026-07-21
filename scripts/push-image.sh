#!/bin/bash
# ============================================================================
# Azure Management Pack — Push image to local registry
#
# Reads the version from manifest.txt (the SINGLE source of truth) and pushes
# the image mp-build produced. No hand-typed tags -> no 8.19.228-vs-233-vs-238
# drift, and no "docker tag: No such image" when the number you typed doesn't
# match what mp-build actually built.
#
# Run AFTER build-pak.sh succeeds and the [MERGE]/[VALIDATE] gates are green.
#
# Usage:
#   bash scripts/push-image.sh                 # tag + push using manifest version
#   bash scripts/push-image.sh --dry-run       # show what it would do, push nothing
#   REGISTRY_TAG=host:5000/repo bash scripts/push-image.sh   # override registry
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# --- Locate manifest.txt (same two-layout logic as build-pak.sh) -----------
if [[ -n "${ADAPTER_DIR:-}" ]]; then
    MANIFEST="${ADAPTER_DIR}/manifest.txt"
elif [[ -f "${SCRIPT_DIR}/../Azure-Native-Build/manifest.txt" ]]; then
    MANIFEST="${SCRIPT_DIR}/../Azure-Native-Build/manifest.txt"
elif [[ -f "${SCRIPT_DIR}/../Azure/manifest.txt" ]]; then
    MANIFEST="${SCRIPT_DIR}/../Azure/manifest.txt"
else
    echo "ERROR: manifest.txt not found. Set ADAPTER_DIR=/path/to/adapter." >&2
    exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.12 || command -v python3)}"

# --- Read version + adapter kind straight from the manifest ----------------
VERSION=$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$MANIFEST")
ADAPTER_KIND=$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["adapter_kinds"][0])' "$MANIFEST")

# mp-build names the image "<adapter_kind lowercased>-test:<version>".
LOCAL_IMAGE="${LOCAL_IMAGE:-$(printf '%s' "$ADAPTER_KIND" | tr '[:upper:]' '[:lower:]')-test}"
REGISTRY_TAG="${REGISTRY_TAG:-214.73.76.134:5000/azuregovcloud-adapter}"

echo "Manifest:        $MANIFEST"
echo "Version:         $VERSION"
echo "Local image:     ${LOCAL_IMAGE}:${VERSION}"
echo "Registry target: ${REGISTRY_TAG}:latest  and  ${REGISTRY_TAG}:${VERSION}"
echo ""

# --- Guard: the exact image mp-build built must exist ----------------------
if ! sudo docker image inspect "${LOCAL_IMAGE}:${VERSION}" >/dev/null 2>&1; then
    echo "ERROR: image ${LOCAL_IMAGE}:${VERSION} not found." >&2
    echo "       The manifest version and the built image are out of sync, or" >&2
    echo "       the build did not finish. Tags currently present:" >&2
    sudo docker images "${LOCAL_IMAGE}" --format '         {{.Repository}}:{{.Tag}}' >&2 || true
    exit 1
fi

if $DRY_RUN; then
    echo "[dry-run] would tag + push:"
    echo "  docker tag ${LOCAL_IMAGE}:${VERSION} ${REGISTRY_TAG}:latest"
    echo "  docker tag ${LOCAL_IMAGE}:${VERSION} ${REGISTRY_TAG}:${VERSION}"
    echo "  docker push ${REGISTRY_TAG}:latest"
    echo "  docker push ${REGISTRY_TAG}:${VERSION}"
    exit 0
fi

# --- Tag both :latest (what the Cloud Proxy pulls) and :<version> ----------
#     The versioned tag gives the registry a traceable history; :latest is
#     what the adapter instance config resolves.
sudo docker tag "${LOCAL_IMAGE}:${VERSION}" "${REGISTRY_TAG}:latest"
sudo docker tag "${LOCAL_IMAGE}:${VERSION}" "${REGISTRY_TAG}:${VERSION}"

sudo docker push "${REGISTRY_TAG}:latest"
sudo docker push "${REGISTRY_TAG}:${VERSION}"

echo ""
echo "=== Pushed ${REGISTRY_TAG}:latest and :${VERSION} ==="
