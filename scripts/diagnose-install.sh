#!/bin/bash
# ============================================================================
# Azure-Native-Build — Install-failure diagnostic
#
# Re-establishes the EXACT reason the pak install fails at Aria Ops
# step 16/20 (APPLY_ADAPTER -> "ERROR after 0.0 seconds", empty errorMessages),
# which means Suite-API rejected describe.xml synchronously.
#
# Run on the MP Builder server (Photon OS), from anywhere in the repo:
#
#   bash scripts/diagnose-install.sh            # Stage A: build + local xmllint validation
#   bash scripts/diagnose-install.sh analytics  # Stage B: pull the real reject from Aria Ops logs
#                                                #          (run AFTER attempting the UI install)
#
# Stage A is fully local (no Aria Ops needed). Read its xmllint block:
#   * schema errors printed  -> STRUCTURAL reject; fix in scripts/patch-describe-xml.py
#     (or the adapter definition) at the exact line/element it names.
#   * "describe.xml validates" -> structurally clean; reject is SEMANTIC. Upload the
#     .pak in the Aria Ops UI, let it fail, then run Stage B (`analytics`).
#
# NOTE: this script does NOT touch git. Sync the server to origin/main yourself
#       first if that's how you transfer it:  git fetch origin && git reset --hard origin/main
#
# Env overrides:
#   REGISTRY_TAG=host:port/repo   # only embedded in the pak; does not affect the xmllint diagnosis
# ============================================================================

set +e  # never abort mid-diagnostic; run every probe even if one fails

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NATIVE_DESCRIBE="$REPO_ROOT/sdk_packages/MicrosoftAzureAdapter-818024067771/AzureAdapter/MicrosoftAzureAdapter/conf/describe.xml"

# ---------------------------------------------------------------------------
# Stage B — pull the real installer reject out of the analytics logs.
# Aria Ops logs the synchronous describe.xml rejection here, not in the UI.
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "analytics" ]]; then
    echo "===== STAGE B: Aria Ops analytics-log reject (last 40 matches) ====="
    sudo grep -hE "Failed to load resource kind describe|Incorrect format in describe.xml|Illegal symbols|addAdapterKind|SAXParse|Self relation" \
        /storage/log/vcops/log/analytics-*.log* 2>/dev/null \
        | grep -vE "ProblemAlertManager|SymptomSetEvaluator|SDDCHealthAdapter" \
        | tail -40
    echo ""
    echo "-- pakManager post_apply_adapter (last 20) --"
    sudo tail -20 /storage/log/vcops/log/pakManager/vcopsPakManager.root.post_apply_adapter.log 2>/dev/null
    echo "===== DONE (Stage B) ====="
    exit 0
fi

# ---------------------------------------------------------------------------
# Stage A — build + local schema validation.
# ---------------------------------------------------------------------------
cd "$REPO_ROOT" || { echo "!! Cannot cd to repo root $REPO_ROOT"; exit 1; }

echo "===== 0. REPO STATE ====="
git log --oneline -1 2>/dev/null || echo "(not a git checkout)"

echo ""
echo "===== 1. CLEAR /tmp-FULL CONDITION (prevents the build-time 500) ====="
# Reap zombie adapter containers from prior failed mp-build/mp-test runs — their
# /tmp lives in host overlay storage and accumulates until tempfile.mkdtemp()
# hits OSError 28, which surfaces as /adapterDefinition returning 500.
sudo docker ps -aq --filter "ancestor=microsoftazureadapter-test" 2>/dev/null | xargs -r sudo docker rm -f
sudo rm -rf /tmp/pak-inspect
sudo find /tmp -maxdepth 1 -type d -name 'tmp*' -exec rm -rf {} + 2>/dev/null
sudo docker system prune -f >/dev/null 2>&1
df -h /tmp /var/lib/docker 2>/dev/null | sed 's/^/   /'

echo ""
echo "===== 2. BUILD PAK ====="
mkdir -p debug
bash scripts/build-pak.sh 2>&1 | tee debug/build.log | tail -8

echo ""
echo "===== 3. EXTRACT + VALIDATE ====="
which xmllint >/dev/null 2>&1 || sudo tdnf install -y libxml2 >/dev/null 2>&1
PAK=$(ls -t Azure-Native-Build/build/*.pak 2>/dev/null | head -1)
echo "PAK=$PAK"
if [[ -z "$PAK" ]]; then
    echo "!! No pak built — the build failed above."
    echo "!! Check debug/build.log for 'adapterDefinition endpoint returned 500' (=/tmp full)"
    echo "!! or a Python traceback naming the crashing kind."
    exit 1
fi

rm -rf /tmp/pak-inspect && mkdir -p /tmp/pak-inspect && cd /tmp/pak-inspect || exit 1
unzip -q "$PAK" && unzip -q adapter.zip
DESCRIBE=$(find . -name describe.xml -not -path '*/conf/describeSchema*' | head -1)
SCHEMA=$(find . -name describeSchema.xsd | head -1)
echo "DESCRIBE=$DESCRIBE"
echo "SCHEMA=$SCHEMA"

echo ""
echo "----- XMLLINT SCHEMA VALIDATION (the decisive output) -----"
xmllint --noout --schema "$SCHEMA" "$DESCRIBE" 2>&1 | head -60

echo ""
echo "----- STRUCTURE -----"
echo "ResourceKind count: $(grep -c '<ResourceKind ' "$DESCRIBE")"
if [[ -f "$NATIVE_DESCRIBE" ]]; then
    echo "(native reference has: $(grep -c '<ResourceKind ' "$NATIVE_DESCRIBE"))"
fi
echo "Root AdapterKind (first 3 lines):"
head -3 "$DESCRIBE" | sed 's/^/   /'

echo ""
echo "----- KNOWN-DEFECT PROBES -----"
echo "pipe-char attribute keys (want 0): $(grep -cE 'ResourceAttribute key="[^\"]*\|' "$DESCRIBE")"
echo "duplicate ResourceKinds (want none):"
grep -oE '<ResourceKind key="[^"]+"' "$DESCRIBE" | sort | uniq -d | sed 's/^/   /'
echo "adapter-instance kind:"
grep 'ResourceKind key="MicrosoftAzureAdapter' "$DESCRIBE" | sed 's/^/   /'

echo ""
echo "===== DONE (Stage A) ====="
echo "If xmllint printed 'validates', upload the .pak in the Aria Ops UI, let it"
echo "fail, then run:  bash scripts/diagnose-install.sh analytics"
