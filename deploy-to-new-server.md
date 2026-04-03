# Full Deployment Guide — MP Builder OVA (Photon OS 4.0)

Everything needed to deploy the Azure Gov management pack from scratch
on the MP Builder 2.0 OVA appliance (Photon 4.0). Installs Python 3.12
alongside the system Python 3.10 for security and SDK compatibility.

---

## Phase 1: Install Missing System Packages (on Photon server)

The MP Builder OVA comes with most packages pre-installed (docker, gcc, python3,
python3-devel, make, and many Python libraries). Only a few are missing.

### 1a: Mount the Photon OS ISO and configure local repo

```bash
sudo mkdir -p /mnt/cdrom
sudo mount /dev/cdrom /mnt/cdrom

# Disable all online repos
sudo sed -i 's/enabled=1/enabled=0/g' /etc/yum.repos.d/*.repo

# Create local repo pointing to mounted ISO
sudo tee /etc/yum.repos.d/cdrom.repo <<EOF
[cdrom]
name=Photon OS CDROM
baseurl=file:///mnt/cdrom/RPMS
gpgcheck=0
enabled=1
EOF

sudo tdnf clean all
sudo tdnf makecache
```

### 1b: Install remaining system packages

```bash
# These may already be installed — tdnf will skip them
sudo tdnf install -y libjpeg-turbo-devel zlib-devel libffi-devel make icu libunwind
```

> **Note:** `git` and `openssl-devel` from the ISO conflict with the OVA's newer OpenSSL 3.0.
> We'll skip git and use SCP to transfer project files instead.

### 1c: Enable and start Docker

```bash
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

Log out and back in for the Docker group to take effect.

### 1d: Create the project directory

```bash
sudo mkdir -p /opt/aria
sudo chmod 777 /opt/aria
```

---

## Phase 2: Install Python 3.12 Alongside System Python (on Photon server)

The OVA ships with Python 3.10. We install 3.12 in `/opt/python312` without
touching the system Python (which the MP Builder appliance depends on).

### 2a: Download Python 3.12 source on Windows PC and transfer

```powershell
curl -L -o C:\Python-3.12.11.tar.xz https://www.python.org/ftp/python/3.12.11/Python-3.12.11.tar.xz
scp C:\Python-3.12.11.tar.xz user@<SERVER>:/opt/aria/Python-3.12.11.tar.xz
```

### 2b: Build and install Python 3.12 on the Photon server

```bash
cd /opt/aria

# Extract
tar xf Python-3.12.11.tar.xz
cd Python-3.12.11

# Build (uses gcc and dev libraries from Phase 1)
./configure --prefix=/opt/python312 --enable-optimizations --with-openssl=/usr
make -j$(nproc)
sudo make altinstall

# Create convenient symlinks
sudo ln -sf /opt/python312/bin/python3.12 /usr/local/bin/python3.12
sudo ln -sf /opt/python312/bin/pip3.12 /usr/local/bin/pip3.12

# Verify
python3.12 --version
pip3.12 --version
```

### 2c: Clean up build files

```bash
cd /opt/aria
rm -rf Python-3.12.11 Python-3.12.11.tar.xz
```

> **Important:** The system `python3` (3.10) is untouched. Always use `python3.12`
> or `pip3.12` explicitly for SDK installs.

---

## Phase 3: Download Offline Packages (on Windows PC with internet)

### 3a: Clone the repo and the SDK source

```powershell
git clone https://github.com/mattmiller03/Aria-MP-Builder.git C:\Aria-MP-Builder
git clone https://github.com/vmware/vmware-aria-operations-integration-sdk.git C:\aria-sdk
```

### 3b: Build and save the base adapter Docker image

```powershell
cd C:\aria-sdk\images\base-python-adapter
docker build -t base-adapter:python-1.2.0 .7

### 3c: Save the Python base image (used inside the adapter container)

```powershell
docker pull python:3.11-slim
docker save python:3.11-slim -o C:\python311slim.tar
```

### 3d: Download PowerShell RPM and Az module

```powershell
# Download PowerShell RPM for Linux x64
# Check https://github.com/PowerShell/PowerShell/releases for latest version
curl -L -o C:\powershell.rpm https://github.com/PowerShell/PowerShell/releases/download/v7.4.6/powershell-7.4.6-1.rh.x86_64.rpm

# Download Az.Accounts module for Azure Gov connectivity testing (run in PowerShell)
mkdir C:\AzModules
Save-Module -Name Az.Accounts -Path C:\AzModules -Repository PSGallery
```

### 3e: Download all Python wheels for offline install

> **Important:** We installed Python **3.12** on the server.
> All wheels with `--python-version` must target 3.12.

```powershell
mkdir C:\aria-wheels

# SDK packages (pure Python — no platform restriction needed)
pip download vmware-aria-operations-integration-sdk -d C:\aria-wheels --no-deps
pip download vmware-aria-operations-integration-sdk-lib -d C:\aria-wheels --no-deps

# SDK dependencies — C extensions for Python 3.12 Linux
# lxml 5.0.0 is the first version with Python 3.12 wheels (uses manylinux_2_28)
pip download "lxml==5.0.0" --python-version 3.12 --platform manylinux_2_28_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "Pillow>=9.3,<11.0" --python-version 3.12 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "cryptography==44.0.0" --python-version 3.12 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "cffi" --python-version 3.12 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "pyyaml" --python-version 3.12 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "markupsafe" --python-version 3.12 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels

# SDK dependencies — pure Python packages
pip download "pycparser" -d C:\aria-wheels --no-deps
pip download "validators==0.18.2" -d C:\aria-wheels --no-deps
pip download "aenum==3.1.11" -d C:\aria-wheels --no-deps
pip download "gitpython" -d C:\aria-wheels --no-deps
pip download "gitdb" -d C:\aria-wheels --no-deps
pip download "smmap" -d C:\aria-wheels --no-deps
pip download "docker>=7.1.0,<8.0.0" -d C:\aria-wheels --no-deps
pip download "httpx>=0.23.0,<0.24.0" -d C:\aria-wheels --no-deps
pip download "httpcore" -d C:\aria-wheels --no-deps
pip download "h11" -d C:\aria-wheels --no-deps
pip download "sniffio" -d C:\aria-wheels --no-deps
pip download "rfc3986" -d C:\aria-wheels --no-deps
pip download "anyio" -d C:\aria-wheels --no-deps
pip download "importlib-metadata>=5.0.0,<6.0.0" -d C:\aria-wheels --no-deps
pip download "importlib-resources==5.13.0" -d C:\aria-wheels --no-deps
pip download "zipp" -d C:\aria-wheels --no-deps
pip download "jsonschema-spec" -d C:\aria-wheels --no-deps
pip download "pathable" -d C:\aria-wheels --no-deps
pip download "openapi-core>=0.15.0,<0.16.0" -d C:\aria-wheels --no-deps
pip download "openapi-schema-validator" -d C:\aria-wheels --no-deps
pip download "openapi-spec-validator" -d C:\aria-wheels --no-deps
pip download "isodate" -d C:\aria-wheels --no-deps
pip download "more-itertools" -d C:\aria-wheels --no-deps
pip download "parse" -d C:\aria-wheels --no-deps
pip download "werkzeug" -d C:\aria-wheels --no-deps
pip download "prompt-toolkit" -d C:\aria-wheels --no-deps
pip download "sen" -d C:\aria-wheels --no-deps
pip download "urwid" -d C:\aria-wheels --no-deps
pip download "urwidtrees" -d C:\aria-wheels --no-deps
pip download "wcwidth" -d C:\aria-wheels --no-deps
pip download "decorator" -d C:\aria-wheels --no-deps
pip download "typing-extensions" -d C:\aria-wheels --no-deps
pip download "xmlschema" -d C:\aria-wheels --no-deps
pip download "elementpath" -d C:\aria-wheels --no-deps
```

### 3f: Transfer everything to the Photon server

```powershell
# Project files (no git needed on server)
scp -r C:\Aria-MP-Builder\Azure user@<SERVER>:/opt/aria/Aria-MP-Builder/Azure
scp C:\Aria-MP-Builder\CLAUDE.md user@<SERVER>:/opt/aria/Aria-MP-Builder/
scp C:\Aria-MP-Builder\README.md user@<SERVER>:/opt/aria/Aria-MP-Builder/
scp C:\Aria-MP-Builder\deploy-to-new-server.md user@<SERVER>:/opt/aria/Aria-MP-Builder/

# Offline packages
scp -r C:\aria-wheels user@<SERVER>:/opt/aria/wheels
scp C:\base-adapter.tar user@<SERVER>:/opt/aria/base-adapter.tar
scp C:\python311slim.tar user@<SERVER>:/opt/aria/python311slim.tar
scp C:\powershell.rpm user@<SERVER>:/opt/aria/powershell.rpm
scp -r C:\AzModules user@<SERVER>:/opt/aria/AzModules
```

---

## Phase 4: Install PowerShell and Test Azure Connectivity (on Photon server)

```bash
# Install PowerShell RPM
sudo rpm -ivh /opt/aria/powershell.rpm

# Verify
pwsh --version

# Install Az.Accounts module
sudo mkdir -p /opt/microsoft/powershell/7/Modules
sudo cp -r /opt/aria/AzModules/* /opt/microsoft/powershell/7/Modules/
```

### Test Azure Gov connectivity

```bash
pwsh
```

Inside PowerShell:

```powershell
Import-Module Az.Accounts

$secret = ConvertTo-SecureString "YOUR_CLIENT_SECRET" -AsPlainText -Force
$cred = New-Object PSCredential("YOUR_CLIENT_ID", $secret)

Connect-AzAccount -Environment AzureUSGovernment -ServicePrincipal -TenantId "YOUR_TENANT_ID" -Credential $cred

# If this returns subscription info, credentials and network connectivity are good
Get-AzSubscription

# Exit PowerShell
exit
```

If this fails, resolve the credential or firewall issue before proceeding — the management pack uses the same endpoints.

---

## Phase 5: Install Aria SDK (on Photon server)

### 5a: Load Docker images

```bash
sudo docker load -i /opt/aria/python311slim.tar
sudo docker load -i /opt/aria/base-adapter.tar

# Verify images loaded
sudo docker images
```

### 5b: Install SDK CLI (without dependency checks to bypass lxml<5.0.0 pin)

```bash
sudo pip3.12 install --no-index --no-deps --find-links /opt/aria/wheels vmware-aria-operations-integration-sdk
```

### 5c: Install SDK runtime library

```bash
sudo pip3.12 install --no-index --find-links /opt/aria/wheels vmware-aria-operations-integration-sdk-lib
```

### 5d: Install lxml 5.0.0 separately (bypasses the SDK's <5.0.0 pin — functionally compatible)

```bash
sudo pip3.12 install --no-index --find-links /opt/aria/wheels lxml
```

### 5e: Install remaining SDK dependencies

```bash
sudo pip3.12 install --no-index --find-links /opt/aria/wheels Pillow cryptography cffi pyyaml gitpython docker httpx prompt-toolkit validators xmlschema
```

> **Note:** If any package fails with a missing dependency, download the specific
> wheel on the Windows PC with `pip download "<package>" -d C:\aria-wheels --no-deps`,
> transfer it to `/opt/aria/wheels/`, and retry.

### 5f: Symlink SDK commands to PATH

```bash
sudo ln -sf /opt/python312/bin/mp-build /usr/local/bin/mp-build
sudo ln -sf /opt/python312/bin/mp-test /usr/local/bin/mp-test
sudo ln -sf /opt/python312/bin/mp-init /usr/local/bin/mp-init
```

### 5g: Verify

```bash
mp-build --version
mp-test --version
```

---

## Phase 6: Fix Line Endings, Permissions, and Configure Credentials (on Photon server)

```bash
cd /opt/aria/Aria-MP-Builder

# Fix CRLF line endings (files come from Windows)
find . -name "*.py" -exec sed -i 's/\r$//' {} +
find . -name "*.sh" -exec sed -i 's/\r$//' {} +
find . -name "*.cfg" -exec sed -i 's/\r$//' {} +
sed -i 's/\r$//' Azure/Dockerfile

# Fix permissions
chmod -R 755 Azure/

# Create connections.json from template
cp Azure/connections.json.example Azure/connections.json
```

### Edit connections.json with your real Azure Gov credentials

```bash
vi Azure/connections.json
```

Replace the YOUR_* placeholders:
- `YOUR_TENANT_ID` — Directory (tenant) ID from Azure Gov Entra ID
- `YOUR_CLIENT_ID` — Application (client) ID from the app registration
- `YOUR_CLIENT_SECRET` — Client secret value
- `YOUR_SUBSCRIPTION_ID` — Target subscription GUID

---

## Phase 7: Create the logs directory

```bash
mkdir -p /opt/aria/Aria-MP-Builder/Azure/logs
chmod 777 /opt/aria/Aria-MP-Builder/Azure/logs
```

---

## Phase 8: Test

```bash
cd /opt/aria/Aria-MP-Builder/Azure

# Find what port is free (8080 may be in use by MP Builder UI)
sudo ss -tlnp | grep 8080
# If 8080 is in use, use 8181 instead

sudo mp-test --port 8181
```

When prompted:
- **Choose a connection:** Azure Gov Test
- **Choose a method to test:** Test Connection

Expected success output:
```
adapterDefinition "HTTP/1.1 200 OK"
endpointURLs "HTTP/1.1 200 OK"
test "HTTP/1.1 200 OK"
Successfully connected. Found X subscription(s).
```

---

## Phase 9: Build the .pak file

```bash
cd /opt/aria/Aria-MP-Builder/Azure
sudo mp-build
```

---

## Phase 10: Deploy to Aria Operations

1. Download the generated `.pak` file from the server
2. In Aria Operations: **Administration > Integrations > Add**
3. Upload the `.pak` file
4. Check **"Ignore the PAK file signature checking"**
5. Accept the EULA
6. Configure adapter instance with Azure Gov credentials
7. Click **Validate Connection**
8. Save and wait 5-15 minutes for first collection

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `pip install` fails with missing package | Download the specific wheel on Windows PC: `pip download "<package>==<version>" -d C:\aria-wheels --no-deps` then SCP to server |
| `pip install` fails with wrong Python version | Re-download with `--python-version 3.12` |
| SDK commands not found after install | Symlink from `/opt/python312/bin/` to `/usr/local/bin/` |
| `python3` still shows 3.10 | Correct — use `python3.12` or `pip3.12` explicitly; don't replace system Python |
| Docker `permission denied` | `sudo usermod -aG docker $USER` then log out/in |
| Port 8080 in use | Use `--port 8181` with mp-test |
| `400 Bad Request` on Azure login | Check credentials in connections.json; test with PowerShell first |
| File permission errors in container | Run `chmod -R 755 Azure/` before mp-test |
| CRLF line ending issues | Run the `sed -i 's/\r$//'` commands from Phase 6 |
| ISO mount says "write-protected" | Normal — ISOs are read-only, the mount worked |
| `git` won't install from ISO | ISO packages conflict with OVA's OpenSSL 3.0; use SCP instead |
