# Commands to Run — Debugging Docker / mp-test

## Step 1: Clean Docker and reload base image

```bash
# Force remove ALL images
sudo docker rmi -f $(sudo docker images -q) 2>/dev/null

# Reload base image from tarball
sudo docker load -i /home/vropsssh/Aria-MP-Builder/Azure/python311slim.tar
```

## Step 2: Investigate how SDK generates its Dockerfile

```bash
# Check for any Dockerfiles the SDK generated
find /home/vropsssh/Aria-MP-Builder -name "Dockerfile*" 2>/dev/null

# Check /tmp for SDK-generated Dockerfiles
find /tmp -name "Dockerfile*" 2>/dev/null

# See how the SDK builds containers — look for Dockerfile, CMD, ENTRYPOINT
grep -n "Dockerfile\|dockerfile\|COPY.*adapter\|CMD\|ENTRYPOINT" /usr/lib/python3.11/site-packages/vmware_aria_operations_integration_sdk/docker_wrapper.py
```

## Step 3: Rebuild and test

```bash
cd /home/vropsssh/Aria-MP-Builder/Azure
sudo mp-test --port 8181
```

## Step 4: If it fails, capture diagnostics

```bash
# Check what container was created
sudo docker ps -a

# Get the container ID from above, then check logs
sudo docker logs <CONTAINER_ID>

# Check what command the container ran
sudo docker inspect <CONTAINER_ID> --format='{{.Config.Cmd}}'
sudo docker inspect <CONTAINER_ID> --format='{{.Config.Entrypoint}}'

# Check what files are in the adapter directory
sudo docker run --rm azuregovcloud-test:1.0.0 ls -la /adapter/

# Check if the SDK lib is installed in the container
sudo docker run --rm azuregovcloud-test:1.0.0 pip list | grep aria
```

## Step 5: Paste all output into ErrorFile.txt


sudo find /usr/lib/python3.11/site-packages/vmware_aria_operations_integration_sdk/ -name "Dockerfile*" 2>/dev/null
sudo cat /usr/lib/python3.11/site-packages/vmware_aria_operations_integration_sdk/container_versions.json 2>/dev/null
sudo find /usr/lib/python3.11/site-packages/vmware_aria_operations_integration_sdk/ -type d -name "images" 2>/dev/null



sudo grep -n "describe\|conf/" /usr/lib/python3.11/site-packages/vmware_aria_operations_integration_sdk/containerized_adapter_rest_api.py


sudo docker run --rm azuregovcloud-test:1.0.0 cat /home/aria-ops-adapter-user/src/app/../../../conf/describe.xml 2>/dev/null || sudo docker run --rm azuregovcloud-test:1.0.0 find / -name "describe.xml" 2>/dev/null
