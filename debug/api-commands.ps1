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