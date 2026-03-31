# Full Deployment Guide — Fresh Photon OS 5.0 Server

Everything needed to deploy the Azure Gov management pack from scratch.
Run these in order.

---

## Phase 1: System Packages (on Photon server)

```bash
sudo tdnf install -y docker git gcc python3-devel libjpeg-turbo-devel zlib-devel libffi-devel openssl-devel make
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

Log out and back in for the Docker group to take effect.

---

## Phase 2: Download Offline Packages (on Windows PC with internet)

### 2a: Clone the repo and the SDK source

```powershell
# Clone our management pack repo
git clone https://github.com/mattmiller03/Aria-MP-Builder.git C:\Aria-MP-Builder

# Clone the SDK repo (needed for the base Docker image)
git clone https://github.com/vmware/vmware-aria-operations-integration-sdk.git C:\aria-sdk
```

### 2b: Build and save the base adapter Docker image

```powershell
cd C:\aria-sdk\images\base-python-adapter
docker build -t base-adapter:python-1.2.0 .
docker save base-adapter:python-1.2.0 -o C:\base-adapter.tar
```

### 2c: Save the Python 3.11 base image

```powershell
docker pull python:3.11-slim
docker save python:3.11-slim -o C:\python311slim.tar
```

### 2d: Download all Python wheels for offline install

```powershell
mkdir C:\aria-wheels

# SDK packages
pip download vmware-aria-operations-integration-sdk --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download vmware-aria-operations-integration-sdk-lib --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels

# C extension wheels
pip download "lxml>=4.9.2,<5.0.0" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "Pillow>=9.3,<11.0" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "cryptography==44.0.0" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "cffi" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "pyyaml" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels

# Pure Python packages
pip download "pycparser" -d C:\aria-wheels --no-deps
pip download "validators==0.18.2" -d C:\aria-wheels --no-deps
pip download "aenum==3.1.11" -d C:\aria-wheels --no-deps
```

### 2e: Create target directory on Photon server

```bash
# SSH to the server first and create the directory
sudo mkdir -p /opt/aria
sudo chmod 777 /opt/aria
```

### 2f: Transfer everything to the Photon server

```powershell
scp -r C:\aria-wheels user@<NEW-SERVER>:/opt/aria/wheels
scp C:\base-adapter.tar user@<NEW-SERVER>:/opt/aria/base-adapter.tar
scp C:\python311slim.tar user@<NEW-SERVER>:/opt/aria/python311slim.tar
```

---

## Phase 3: Install SDK (on Photon server)

```bash
# Load Docker images
sudo docker load -i /opt/aria/python311slim.tar
sudo docker load -i /opt/aria/base-adapter.tar

# Verify images loaded
sudo docker images

# Install the SDK and runtime library
sudo pip install --no-index --find-links /opt/aria/wheels vmware-aria-operations-integration-sdk
sudo pip install --no-index --find-links /opt/aria/wheels vmware-aria-operations-integration-sdk-lib

# Verify
mp-build --version
mp-test --version
```

---

## Phase 4: Clone and Configure the Management Pack (on Photon server)

```bash
cd /opt/aria
git clone https://github.com/mattmiller03/Aria-MP-Builder.git
cd Aria-MP-Builder

# Fix line endings and permissions
find . -name "*.py" -exec sed -i 's/\r$//' {} +
find . -name "*.sh" -exec sed -i 's/\r$//' {} +
find . -name "*.cfg" -exec sed -i 's/\r$//' {} +
sed -i 's/\r$//' Azure/Dockerfile
chmod -R 755 Azure/

# Create connections.json from template
cp Azure/connections.json.example Azure/connections.json
```

### Edit connections.json with your real Azure Gov credentials:

```bash
vi Azure/connections.json
```

Replace the YOUR_* placeholders:
- `YOUR_TENANT_ID` — Directory (tenant) ID from Azure Gov Entra ID
- `YOUR_CLIENT_ID` — Application (client) ID from the app registration
- `YOUR_CLIENT_SECRET` — Client secret value
- `YOUR_SUBSCRIPTION_ID` — Target subscription GUID

---

## Phase 5: Create the logs directory

```bash
mkdir -p /opt/aria/Aria-MP-Builder/Azure/logs
chmod 777 /opt/aria/Aria-MP-Builder/Azure/logs
```

---

## Phase 6: Test

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

## Phase 7: Build the .pak file

```bash
cd /opt/aria/Aria-MP-Builder/Azure
sudo mp-build
```

---

## Phase 8: Deploy to Aria Operations

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
| `pip install` fails with missing package | Download the specific wheel on Windows PC and transfer |
| Docker `permission denied` | `sudo usermod -aG docker $USER` then log out/in |
| Port 8080 in use | Use `--port 8181` with mp-test |
| `400 Bad Request` on Azure login | Check credentials in connections.json |
| File permission errors in container | Run `chmod -R 755 Azure/` before mp-test |
| CRLF line ending issues | Run the `sed -i 's/\r$//'` commands from Phase 4 |
