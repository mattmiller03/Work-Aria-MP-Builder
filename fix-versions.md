# Fix Package Versions

## On Windows PC — download correct versions

```powershell
pip download "sen==0.6.2" -d C:\aria-wheels --no-deps
pip download "validators==0.20.0" -d C:\aria-wheels --no-deps
pip download "xmlschema==2.4.0" -d C:\aria-wheels --no-deps
pip download "elementpath==4.4.0" -d C:\aria-wheels --no-deps
pip download "setuptools==78.1.1" -d C:\aria-wheels --no-deps
```

## Transfer to server

```powershell
scp C:\aria-wheels\sen-0.6.2* user@<SERVER>:/opt/aria/wheels/
scp C:\aria-wheels\validators-0.20.0* user@<SERVER>:/opt/aria/wheels/
scp C:\aria-wheels\xmlschema-2.4.0* user@<SERVER>:/opt/aria/wheels/
scp C:\aria-wheels\elementpath-4.4.0* user@<SERVER>:/opt/aria/wheels/
scp C:\aria-wheels\setuptools-78.1.1* user@<SERVER>:/opt/aria/wheels/
```

## On Photon server — install correct versions

```bash
pip3.12 install --force-reinstall --no-index --find-links /opt/aria/wheels "sen==0.6.2"
pip3.12 install --force-reinstall --no-index --find-links /opt/aria/wheels "validators==0.20.0"
pip3.12 install --force-reinstall --no-index --find-links /opt/aria/wheels "xmlschema==2.4.0"
pip3.12 install --force-reinstall --no-index --find-links /opt/aria/wheels "setuptools==78.1.1"
```

## Verify

```bash
mp-build --version
mp-test --version
```



sudo docker rmi azuregovcloud-test:1.0.0 2>/dev/null
sudo docker rmi $(sudo docker images -q --filter "label=mp-test") 2>/dev/null

# Verify latest files have correct permissions and line endings
find /opt/aria/Aria-MP-Builder/Azure -name "*.py" -exec sed -i 's/\r$//' {} +
sed -i 's/\r$//' /opt/aria/Aria-MP-Builder/Azure/Dockerfile
sed -i 's/\r$//' /opt/aria/Aria-MP-Builder/Azure/commands.cfg
chmod -R 755 /opt/aria/Aria-MP-Builder/Azure/

# Retry
cd /opt/aria/Aria-MP-Builder/Azure
sudo mp-test --port 8080


The build needs the conf/ directory with the XSD schema file. The SDK uses this for validation during build. Create the directory and let the build generate what it needs:


mkdir -p /opt/aria/Aria-MP-Builder/Azure/conf
Then check if the SDK has the schema file bundled somewhere:


sudo find /opt/python312/lib/python3.12/site-packages/vmware_aria_operations_integration_sdk/ -name "*.xsd" 2>/dev/null
If it finds a describeSchema.xsd, copy it:


sudo cp <path_from_above>/describeSchema.xsd /opt/aria/Aria-MP-Builder/Azure/conf/
If no XSD exists, the build should still work — it's just a validation step. Try the build again:


cd /opt/aria/Aria-MP-Builder/Azure
sudo mp-build



The SDK wants to push the adapter image to a container registry as part of the build. On air-gapped environments, we can run a local registry in Docker and point to that:


# Start a local Docker registry
sudo docker run -d -p 5000:5000 --restart=always --name registry registry:2 2>/dev/null

# If the registry image isn't available (air-gapped), skip it and use --no-ttl with the registry tag
cd /opt/aria/Aria-MP-Builder/Azure
sudo mp-build --no-ttl --registry-tag "localhost:5000/azuregovcloud" --use-default-registry -P 8080
If the local registry isn't available either, try forcing it all on the command line to skip the interactive prompts:


sudo mp-build --no-ttl --use-default-registry -P 8080
If it still prompts for the registry path, we may need to create a config file. Check if there's a config file the SDK reads:


cat /opt/aria/Aria-MP-Builder/Azure/config.json 2>/dev/null
ls /opt/aria/Aria-MP-Builder/Azure/*.json