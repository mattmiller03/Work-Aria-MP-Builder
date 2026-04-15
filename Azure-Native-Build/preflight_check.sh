#!/bin/bash
# ============================================================================
# Aria Operations Management Pack — Azure Gov Cloud
# Preflight Prerequisites Check
#
# Run this on your Photon OS server before building/testing the pack:
#   chmod +x preflight_check.sh && ./preflight_check.sh
# ============================================================================

PASS=0
FAIL=0
WARN=0

pass()  { echo "  [PASS]  $1"; PASS=$((PASS + 1)); }
fail()  { echo "  [FAIL]  $1"; FAIL=$((FAIL + 1)); }
warn()  { echo "  [WARN]  $1"; WARN=$((WARN + 1)); }
header(){ echo ""; echo "=== $1 ==="; }

# ---------- OS ----------
header "Operating System"

if [ -f /etc/photon-release ]; then
    VERSION=$(cat /etc/photon-release)
    pass "Photon OS detected: $VERSION"
else
    warn "Not running on Photon OS (detected: $(uname -s)). This may still work."
fi

# ---------- Python ----------
header "Python"

if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version 2>&1)
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 8 ]; then
        pass "$PY_VERSION (>= 3.8 required)"
    else
        fail "$PY_VERSION — Python 3.8+ is required. Run: tdnf install python3 -y"
    fi
else
    fail "python3 not found. Run: tdnf install python3 -y"
fi

if command -v pip3 &>/dev/null || command -v pip &>/dev/null; then
    PIP_CMD=$(command -v pip3 || command -v pip)
    PIP_VERSION=$($PIP_CMD --version 2>&1 | head -1)
    pass "pip found: $PIP_VERSION"
else
    fail "pip not found. Run: tdnf install python3-pip -y"
fi

# ---------- Docker ----------
header "Docker"

if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version 2>&1)
    pass "$DOCKER_VERSION"
else
    fail "Docker not found. Run: tdnf install docker -y"
fi

if systemctl is-active docker &>/dev/null; then
    pass "Docker service is running"
else
    fail "Docker service is not running. Run: systemctl enable docker && systemctl start docker"
fi

if docker info &>/dev/null 2>&1; then
    pass "Current user can access Docker"
else
    fail "Cannot access Docker. Run: usermod -aG docker \$USER (then log out/in)"
fi

# ---------- Git ----------
header "Git"

if command -v git &>/dev/null; then
    GIT_VERSION=$(git --version 2>&1)
    pass "$GIT_VERSION"
else
    fail "Git not found. Run: tdnf install git -y"
fi

# ---------- VCF Operations Integration SDK ----------
header "VCF Operations Integration SDK"

if command -v mp-build &>/dev/null; then
    pass "mp-build found: $(command -v mp-build)"
else
    fail "mp-build not found. Run: pip install vmware-aria-operations-integration-sdk"
fi

if command -v mp-test &>/dev/null; then
    pass "mp-test found: $(command -v mp-test)"
else
    fail "mp-test not found. Run: pip install vmware-aria-operations-integration-sdk"
fi

if command -v mp-init &>/dev/null; then
    pass "mp-init found: $(command -v mp-init)"
else
    fail "mp-init not found. Run: pip install vmware-aria-operations-integration-sdk"
fi

# ---------- Python Dependencies ----------
header "Python Dependencies"

if python3 -c "import requests" &>/dev/null 2>&1; then
    REQ_VERSION=$(python3 -c "from importlib.metadata import version; print(version('requests'))" 2>/dev/null || echo "unknown")
    pass "requests library installed: v$REQ_VERSION"
else
    fail "requests library not found. Run: pip install -r Azure/app/requirements.txt"
fi

# ---------- Project Files ----------
header "Project Files"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Script lives inside Azure/ — if we detect app/adapter.py here, use SCRIPT_DIR directly
# Otherwise assume we're in the repo root and look for Azure/
if [ -f "$SCRIPT_DIR/app/adapter.py" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
elif [ -f "$SCRIPT_DIR/Azure/app/adapter.py" ]; then
    PROJECT_DIR="$SCRIPT_DIR/Azure"
else
    PROJECT_DIR="$SCRIPT_DIR"
fi

check_file() {
    if [ -f "$PROJECT_DIR/$1" ]; then
        pass "$1 exists"
    else
        fail "$1 missing — repository may be incomplete"
    fi
}

check_file "app/adapter.py"
check_file "app/auth.py"
check_file "app/azure_client.py"
check_file "app/constants.py"
check_file "app/collectors/__init__.py"
check_file "app/requirements.txt"
check_file "conf/describe.xml"
check_file "manifest.txt"
check_file "resources/resources.properties"
check_file "eula.txt"

# ---------- Credentials ----------
header "Credentials Configuration"

if [ -f "$PROJECT_DIR/connections.json" ]; then
    # Check if placeholders are still in place
    if grep -q "YOUR_TENANT_ID" "$PROJECT_DIR/connections.json" 2>/dev/null; then
        warn "connections.json still has placeholder values — update with real Azure Gov credentials before testing"
    else
        pass "connections.json configured (placeholders replaced)"
    fi
else
    fail "connections.json not found. Copy the template and fill in your Azure Gov credentials:
         cp connections.json.example connections.json"
fi

# ---------- Network Connectivity ----------
header "Network Connectivity (Azure Gov Endpoints)"

check_endpoint() {
    local HOST=$1
    local PORT=${2:-443}
    local DESC=$3
    if timeout 5 bash -c "echo >/dev/tcp/$HOST/$PORT" 2>/dev/null; then
        pass "$DESC — $HOST:$PORT reachable"
    else
        fail "$DESC — cannot reach $HOST:$PORT. Check firewall/proxy rules."
    fi
}

check_endpoint "login.microsoftonline.us"   443 "Azure Gov Auth"
check_endpoint "management.usgovcloudapi.net" 443 "Azure Gov ARM"

# ---------- Summary ----------
header "SUMMARY"
echo ""
echo "  Passed:   $PASS"
echo "  Failed:   $FAIL"
echo "  Warnings: $WARN"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo "  ✓ All checks passed. You are ready to build and test the management pack."
    echo ""
    echo "  Next steps:"
    echo "    cd Azure"
    echo "    mp-test       # Test locally against Azure Gov"
    echo "    mp-build      # Build the .pak file"
    echo ""
    exit 0
else
    echo "  ✗ $FAIL check(s) failed. Resolve the issues above before proceeding."
    echo ""
    exit 1
fi
