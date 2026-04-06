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


The SDK insists on a registry login. Since you're air-gapped, let's set up a local registry that needs no authentication. First check if you have the registry image from the old server, or if it's bundled:


sudo docker images | grep registry
If nothing shows, we need to get the registry image. But there's a simpler workaround — create a fake Docker Hub login so mp-build stops complaining:


# Create a Docker Hub account config (doesn't need to be real for local builds)
mkdir -p /root/.docker
echo '{"auths":{"https://index.docker.io/v1/":{"auth":"ZmFrZTpmYWtl"}}}' > /root/.docker/config.json

# Now run mp-build with a Docker Hub path
cd /opt/aria/Aria-MP-Builder/Azure
sudo mp-build --no-ttl --registry-tag "azuregovcloud/adapter" --use-default-registry -P 8080
The ZmFrZTpmYWtl is just base64 of fake:fake — the push will fail but by then the .pak should already be generated since --use-default-registry tells the pack to pull from Aria's internal registry at runtime anyway. The push step happens after the .pak is created.



The SDK always tries to login to a registry before building — can't skip it on an air-gapped server. Let me check the source to find a way around this:


sudo grep -n "login\|Login\|registry\|Registry" /opt/python312/lib/python3.12/site-packages/vmware_aria_operations_integration_sdk/mp_build.py | head -30
Share that output. In the meantime, the alternative is to build the .pak on your Windows PC (which has internet) instead of the air-gapped server. You have Docker Desktop there and it can reach Docker Hub.

On your Windows PC:


cd "C:\Users\mille\OneDrive\Documents\GitHub\Aria\MP Builder\Azure"
pip install vmware-aria-operations-integration-sdk
mp-build --use-default-registry -P 8080
This might be the path of least resistance since Docker Hub login will work from your Windows PC.


I see it. The is_valid_registry function on line 137 checks if it looks like a Docker Hub format (line 161) and if so, tries to login. For a localhost:5000 registry, it would skip Docker Hub login — but the registry container isn't running since the image wasn't available.

The quickest fix: patch the login function to skip on the air-gapped server:


sudo python3.12 -c "
import vmware_aria_operations_integration_sdk.mp_build as mb
import inspect
print(inspect.getfile(mb))
"
Then patch the login call:


sudo sed -i 's/login(\*\*kwargs)/pass  # login(**kwargs) - skipped for air-gapped/' /opt/python312/lib/python3.12/site-packages/vmware_aria_operations_integration_sdk/mp_build.py
sudo sed -i 's/login(container_registry=container_registry, \*\*kwargs)/pass  # login skipped for air-gapped/' /opt/python312/lib/python3.12/site-packages/vmware_aria_operations_integration_sdk/mp_build.py
Then provide a local registry tag and fake credentials:


cd /opt/aria/Aria-MP-Builder/Azure
sudo mp-build --no-ttl --registry-tag "localhost:5000/azuregovcloud" --registry-username "fake" --registry-password "fake" --use-default-registry -P 8080
The login calls are now no-ops, so it won't try to reach Docker Hub or any registry. The --use-default-registry flag means the .pak tells Aria Operations to use its built-in registry anyway.



# Get auth token
$body = '{"username":"admin","password":"YOUR_PASSWORD"}'
$token = (Invoke-RestMethod -Uri "https://<aria-ops-fqdn>/suite-api/api/auth/token/acquire" -Method Post -Body $body -ContentType "application/json" -SkipCertificateCheck).token

# Upload pak and capture full response
$headers = @{ "Authorization" = "vRealizeOpsToken $token"; "Content-Type" = "application/octet-stream" }
try {
    Invoke-RestMethod -Uri "https://<aria-ops-fqdn>/suite-api/api/solutions/pak" -Method Post -Headers $headers -InFile "C:\path\to\AzureGovCloud_1.0.0.pak" -SkipCertificateCheck -Verbose
} catch {
    $_.Exception.Message
    $_.ErrorDetails.Message
}


405 means the endpoint path is wrong. The API for Aria Ops 8.18 might use a different path. Let me find it:


# Check available pak/solution endpoints
$headers = @{ "Authorization" = "vRealizeOpsToken $token"; "Accept" = "application/json" }

# Try listing existing solutions first
Invoke-RestMethod -Uri "https://<aria-ops-fqdn>/suite-api/api/solutions" -Method Get -Headers $headers -SkipCertificateCheck
Also try the upload with multipart form data instead of octet-stream, and a different endpoint:


# Try alternate endpoint paths
try {
    Invoke-RestMethod -Uri "https://<aria-ops-fqdn>/suite-api/api/solutions/pak/upload" -Method Post -Headers @{ "Authorization" = "vRealizeOpsToken $token" } -Form @{ file = Get-Item "C:\path\to\AzureGovCloud_1.0.0.pak" } -SkipCertificateCheck
} catch {
    $_.Exception.Message
    $_.ErrorDetails.Message
}