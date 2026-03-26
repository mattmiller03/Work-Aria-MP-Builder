# Commands to Run — SDK Offline Install

## Step 1: On Windows PC (internet connected)

Download all required wheels for Linux Python 3.11:

```powershell
# SDK and pure-Python dependencies
pip download vmware-aria-operations-integration-sdk --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download vmware-aria-operations-integration-sdk-lib --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels

# C extension wheels (platform-specific)
pip download "lxml>=4.9.2,<5.0.0" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "Pillow>=9.3,<11.0" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "cryptography==44.0.0" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "cffi" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels
pip download "pyyaml" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels

# Pure Python packages (no platform restriction needed)
pip download "pycparser" -d C:\aria-wheels --no-deps
pip download "validators==0.18.2" -d C:\aria-wheels --no-deps
```

## Step 2: Transfer to Photon Server

```powershell
scp -r C:\aria-wheels vropsssh@<photon-server>:/home/vropsssh/Aria-MP-Builder/aria-wheels
```

## Step 3: Install on Photon Server (air-gapped)

```bash
cd /home/vropsssh/Aria-MP-Builder

# Install SDK CLI tools (mp-build, mp-test, mp-init)
sudo pip install --no-index --find-links /home/vropsssh/Aria-MP-Builder/aria-wheels vmware-aria-operations-integration-sdk

# Install SDK runtime library (used by adapter.py)
sudo pip install --no-index --find-links /home/vropsssh/Aria-MP-Builder/aria-wheels vmware-aria-operations-integration-sdk-lib
```

## Step 4: Verify

```bash
mp-build --version
mp-test --version
pip show vmware-aria-operations-integration-sdk
pip show vmware-aria-operations-integration-sdk-lib
pip show pillow
pip show lxml
pip show cryptography
```

## Step 5: Run Preflight Check

```bash
cd /home/vropsssh/Aria-MP-Builder
sed -i 's/\r$//' Azure/preflight_check.sh
chmod +x Azure/preflight_check.sh
./Azure/preflight_check.sh
```

## Troubleshooting

If install fails with `No matching distribution found for <package>`:

1. Note the exact package name and version from the error
2. On the Windows PC, download it:

   ```powershell
   # For C extensions (lxml, Pillow, cryptography, cffi, pyyaml, etc.)
   pip download "<package>==<version>" --python-version 3.11 --platform manylinux2014_x86_64 --only-binary=:all: -d C:\aria-wheels

   # For pure Python packages (if the above fails with "no matching distribution")
   pip download "<package>==<version>" -d C:\aria-wheels --no-deps
   ```

3. Transfer the new wheel to the Photon server
4. Retry the install
