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


 /opt/aria/Aria-MP-Builder/Azure ]# sudo grep -n "login\|Login\|registry\|Registry" /opt/python312/lib/python3.12/site-packages/vmware_aria_operations_integration_sdk/mp_build.py | head -30
59:from vmware_aria_operations_integration_sdk.docker_wrapper import login
60:from vmware_aria_operations_integration_sdk.docker_wrapper import LoginError
82:    ContainerRegistryValidator,
137:def is_valid_registry(container_registry: str, **kwargs: Any) -> bool:
139:        if _is_docker_hub_registry_format(container_registry):
140:            if "registry_username" not in kwargs:
141:                kwargs["registry_username"] = prompt("Enter Docker Hub username: ")
143:            if "registry_password" not in kwargs:
144:                kwargs["registry_password"] = prompt("Password: ", is_password=True)
145:            login(**kwargs)
147:            container_registry = (
148:                container_registry
149:                if container_registry.startswith("docker.io")
150:                else f"docker.io/{container_registry}"
153:        login(container_registry=container_registry, **kwargs)
155:    except LoginError:
161:def _is_docker_hub_registry_format(registry: Optional[str]) -> bool:
162:    if not registry:
169:    return bool(re.match(pattern, registry))
174:    container_push_registry_arg: Optional[str],
175:    container_registry_arg: Optional[str],
182:    container_registry = container_registry_arg
183:    if not container_registry:
184:        container_registry = get_config_value(
187:    container_push_registry = container_push_registry_arg
188:    if not container_push_registry:
189:        container_push_registry = get_config_value(
192:    if not container_push_registry:
193:        container_push_registry = container_registry
196:    original_value = container_registry