# Aria Operations REST API — PAK Upload Commands
# Run these on a machine that can reach the Aria Ops server

# ============================================================
# Step 1: Get auth token
# ============================================================
$ariaOps = "https://<ARIA-OPS-FQDN>"

$body = @{
    username = "admin"
    password = "<YOUR_PASSWORD>"
    authSource = "LOCAL"
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri "$ariaOps/suite-api/api/auth/token/acquire" -Method Post -Body $body -ContentType "application/json" -SkipCertificateCheck
$token = $result.'auth-token'.token
Write-Host "Token: $token"

# ============================================================
# Step 2: List existing solutions (verify API works)
# ============================================================
$headers = @{
    "Authorization" = "vRealizeOpsToken $token"
    "Accept" = "application/json"
}

Invoke-RestMethod -Uri "$ariaOps/suite-api/api/solutions" -Method Get -Headers $headers -SkipCertificateCheck

# ============================================================
# Step 3: Upload PAK file (try different endpoints)
# ============================================================

# --- Attempt A: POST to /pak ---
try {
    Invoke-RestMethod -Uri "$ariaOps/suite-api/api/solutions/pak" -Method Post -Headers @{
        "Authorization" = "vRealizeOpsToken $token"
        "Content-Type" = "application/octet-stream"
    } -InFile "C:\Users\mille\OneDrive\Documents\GitHub\Aria\MP Builder\Azure\build\AzureGovCloud_1.0.0.pak" -SkipCertificateCheck -Verbose
    Write-Host "Attempt A succeeded"
} catch {
    Write-Host "Attempt A failed: $($_.Exception.Message)"
    Write-Host "Details: $($_.ErrorDetails.Message)"
}

# --- Attempt B: POST to /pak/upload ---
try {
    Invoke-RestMethod -Uri "$ariaOps/suite-api/api/solutions/pak/upload" -Method Post -Headers @{
        "Authorization" = "vRealizeOpsToken $token"
    } -Form @{
        file = Get-Item "C:\Users\mille\OneDrive\Documents\GitHub\Aria\MP Builder\Azure\build\AzureGovCloud_1.0.0.pak"
    } -SkipCertificateCheck -Verbose
    Write-Host "Attempt B succeeded"
} catch {
    Write-Host "Attempt B failed: $($_.Exception.Message)"
    Write-Host "Details: $($_.ErrorDetails.Message)"
}

# --- Attempt C: PUT to /pak ---
try {
    Invoke-RestMethod -Uri "$ariaOps/suite-api/api/solutions/pak" -Method Put -Headers @{
        "Authorization" = "vRealizeOpsToken $token"
        "Content-Type" = "application/octet-stream"
    } -InFile "C:\Users\mille\OneDrive\Documents\GitHub\Aria\MP Builder\Azure\build\AzureGovCloud_1.0.0.pak" -SkipCertificateCheck -Verbose
    Write-Host "Attempt C succeeded"
} catch {
    Write-Host "Attempt C failed: $($_.Exception.Message)"
    Write-Host "Details: $($_.ErrorDetails.Message)"
}

# --- Attempt D: POST multipart to /pak ---
try {
    $pakBytes = [System.IO.File]::ReadAllBytes("C:\Users\mille\OneDrive\Documents\GitHub\Aria\MP Builder\Azure\build\AzureGovCloud_1.0.0.pak")
    Invoke-RestMethod -Uri "$ariaOps/suite-api/api/solutions/pak" -Method Post -Headers @{
        "Authorization" = "vRealizeOpsToken $token"
        "Content-Type" = "multipart/form-data"
    } -Body $pakBytes -SkipCertificateCheck -Verbose
    Write-Host "Attempt D succeeded"
} catch {
    Write-Host "Attempt D failed: $($_.Exception.Message)"
    Write-Host "Details: $($_.ErrorDetails.Message)"
}

# ============================================================
# Step 4: Check upload status (if any attempt returned a pak_id)
# ============================================================
# $pakId = "<pak_id_from_response>"
# Invoke-RestMethod -Uri "$ariaOps/suite-api/api/solutions/pak/$pakId/status" -Method Get -Headers $headers -SkipCertificateCheck


# Check what API endpoints exist for solutions
$headers = @{ "Authorization" = "vRealizeOpsToken $token"; "Accept" = "application/json" }

# List solution API options
try { Invoke-RestMethod -Uri "$ariaOps/suite-api/api/solutions" -Method Options -Headers $headers -SkipCertificateCheck } catch { $_.Exception.Message }

# Check if there's a container adapter endpoint
try { Invoke-RestMethod -Uri "$ariaOps/suite-api/api/adapters" -Method Get -Headers $headers -SkipCertificateCheck } catch { $_.Exception.Message }

# Try the internal API endpoint
try { Invoke-RestMethod -Uri "$ariaOps/casa/pak/upload" -Method Post -Headers @{ "Authorization" = "vRealizeOpsToken $token"; "Content-Type" = "application/octet-stream" } -InFile "C:\Users\mille\OneDrive\Documents\GitHub\Aria\MP Builder\Azure\build\AzureGovCloud_1.0.0.pak" -SkipCertificateCheck -Verbose } catch { Write-Host "casa: $($_.Exception.Message)"; Write-Host "Details: $($_.ErrorDetails.Message)" }


# First, see the structure of existing adapters
$headers = @{ "Authorization" = "vRealizeOpsToken $token"; "Accept" = "application/json" }
$adapters = Invoke-RestMethod -Uri "$ariaOps/suite-api/api/adapters" -Method Get -Headers $headers -SkipCertificateCheck
$adapters.adapterInstancesInfoDto | Select-Object -First 3 | ConvertTo-Json -Depth 5



# Add the insecure registry
sudo tee /etc/docker/daemon.json <<EOF
{
  "insecure-registries": ["<MP-BUILDER-IP>:5000"]
}
EOF

# Restart Docker
sudo systemctl restart docker

# Re-start the registry container (it stopped when Docker restarted)
sudo docker start registry

# Retry the push
sudo docker push <MP-BUILDER-IP>:5000/azuregovcloud-adapter:1.0.0



cd /opt/aria/Aria-MP-Builder/Azure

# Update config.json to point at local registry
cat > config.json <<EOF
{
    "container_push_repository": null,
    "container_repository": "<MP-BUILDER-IP>:5000/azuregovcloud-adapter",
    "default_memory_limit": 1024,
    "use_default_registry": false
}
EOF

# Patch mp-build to skip login (we already pushed the image)
sudo sed -i 's/login(\*\*kwargs)/pass  # login skipped/' /opt/python312/lib/python3.12/site-packages/vmware_aria_operations_integration_sdk/mp_build.py
sudo sed -i 's/login(container_registry=container_registry, \*\*kwargs)/pass  # login skipped/' /opt/python312/lib/python3.12/site-packages/vmware_aria_operations_integration_sdk/mp_build.py

# Clean and rebuild
rm -rf build
sudo mp-build --no-ttl --registry-tag "<MP-BUILDER-IP>:5000/azuregovcloud-adapter" -P 8080



cat > /opt/aria/Aria-MP-Builder/Azure/manifest.txt <<EOF
{
  "name": "AzureGovCloud",
  "version": "1.0.0",
  "vcops_minimum_version": "8.10.0",
  "adapter_kinds": ["AzureGovAdapter"],
  "description": "Collects resource attributes from Azure Government Cloud including VMs, Disks, Networks, Storage, Key Vaults, SQL, and App Services.",
  "vendor": "Custom",
  "eula_file": "eula.txt",
  "pak_icon": "icon.png",
  "pak_validation_script": {
    "script": "",
    "script_timeout": 360
  },
  "adapter_pre_script": {
    "script": "",
    "script_timeout": 360
  },
  "adapter_post_script": {
    "script": "",
    "script_timeout": 360
  },
  "platform": ["Linux"]
}
EOF
