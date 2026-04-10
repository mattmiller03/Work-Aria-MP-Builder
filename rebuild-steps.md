# Management Pack Rebuild — Step by Step

Every time you update the adapter code and need to redeploy.

---

## Step 1: Update the version (on MP Builder server)

```bash
vi /opt/aria/Aria-MP-Builder/Azure/manifest.txt
```

Bump the `"version"` field (e.g., `1.1.0` to `1.2.0`).

---

## Step 2: Build the .pak

```bash
cd /opt/aria/Aria-MP-Builder/Azure
rm -rf build
sudo mp-build -i --no-ttl --registry-tag "214.73.76.134:5000/azuregovcloud-adapter" -P 8181
```

Wait for it to finish.

---

## Step 3: Tag and push the new image to the local registry

```bash
sudo docker tag azuregovcloud-test:<VERSION> 214.73.76.134:5000/azuregovcloud-adapter:latest
sudo docker push 214.73.76.134:5000/azuregovcloud-adapter:latest
```

Replace `<VERSION>` with whatever version `docker images | grep azure` shows.

---

## Step 4: Verify the .pak conf looks right

```bash
cd /tmp && rm -rf azuregov-pak adapter-check
cp /opt/aria/Aria-MP-Builder/Azure/build/*.pak /tmp/azuregov.zip
unzip -o azuregov.zip -d azuregov-pak
unzip -o azuregov-pak/adapter.zip -d adapter-check
cat adapter-check/AzureGovAdapter.conf
```

Should show:
- `REGISTRY=214.73.76.134`
- `API_PORT=8080`
- `API_PROTOCOL=http`

If `API_PORT=443` or `API_PROTOCOL=https`, the `-i` flag didn't take effect. Do NOT manually edit — re-run Step 2 with `-i`.

---

## Step 5: Transfer the .pak to a machine that can access the Aria Ops UI

```bash
scp /opt/aria/Aria-MP-Builder/Azure/build/*.pak user@<YOUR-PC>:/path/to/download/
```

Or use WinSCP / USB drive.

---

## Step 6: Upload to Aria Operations

1. Log in to Aria Ops UI
2. Go to the integrations page where you previously installed the pack
3. If upgrading: find the existing AzureGovCloud adapter and click **Upgrade** (upload the new .pak)
4. If fresh install: **Add** > upload .pak > check **ignore unsigned** > accept EULA
5. Wait for install to complete

---

## Step 7: Pull new image on Cloud Proxy

```bash
# SSH to the Cloud Proxy
sudo docker pull 214.73.76.134:5000/azuregovcloud-adapter:latest
```

---

## Step 8: Validate Connection

1. In Aria Ops UI, go to the adapter account
2. Click **Validate Connection**
3. Should succeed within 30 seconds

---

## Step 9: Verify on Cloud Proxy

```bash
# Check container is running
sudo docker ps | grep azure

# Check logs look healthy
sudo docker logs $(sudo docker ps -q --filter name=dockerized_adapter) 2>&1 | tail -10
```

Should show `Uvicorn running on http://0.0.0.0:8080`.

---

## Quick Reference — Common Issues

| Problem | Fix |
|---------|-----|
| Validate times out | Check `docker ps` on Cloud Proxy — is container running? |
| Container runs but no connection | Check `.pak` conf has `API_PORT=8080` and `API_PROTOCOL=http` |
| Old image still in use | `docker pull` on Cloud Proxy, or use Upgrade option in UI |
| `harbor-repo.vmware.com` errors | `.pak` conf missing `REGISTRY=` line — rebuild |
| Port 443 conflict | Rebuild with `-i` flag |
