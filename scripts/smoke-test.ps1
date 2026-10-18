# smoke-test.ps1 - Automated verification of running schemawatch instance
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"

if (-not (Test-Path $envFile)) {
    Write-Error "ERROR: .env file not found in $root. Run .\scripts\setup.ps1 first."
    exit 1
}

$token = $null
$lines = Get-Content -Path $envFile
foreach ($line in $lines) {
    if ($line -match '^SCHEMAWATCH_API_TOKEN=(.+)$') {
        $token = $Matches[1].Trim()
        break
    }
}

if (-not $token -or $token -eq "your-random-secure-token-here") {
    Write-Error "ERROR: Valid SCHEMAWATCH_API_TOKEN not found in .env. Run .\scripts\setup.ps1 to generate one."
    exit 1
}

Write-Host "Waiting for schemawatch to become healthy at http://localhost:8000/healthz (timeout 60s)..."
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $res = Invoke-RestMethod -Uri "http://localhost:8000/healthz" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($res.status -eq "ok") {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $healthy) {
    Write-Host "FAIL: schemawatch failed to become healthy at http://localhost:8000/healthz within 60s"
    exit 1
}
Write-Host "Service is healthy!"

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
}

$runId = [System.Guid]::NewGuid().ToString("N").Substring(0, 8)
$endpoint = "GET /v1/smoke-$runId"

Write-Host "Sending 10 normal baseline learning samples to $endpoint..."
for ($i = 1; $i -le 10; $i++) {
    $payloadObj = @{
        vendor   = "payco"
        endpoint = $endpoint
        payload  = @{
            user_id = $i
            amount  = 10.5
        }
    }
    $body = $payloadObj | ConvertTo-Json
    $null = Invoke-RestMethod -Uri "http://localhost:8000/api/ingest" -Method Post -Headers $headers -Body $body -ContentType "application/json"
}

Write-Host "Sending 1 type-drift sample (user_id changed from integer to string)..."
$driftObj = @{
    vendor   = "payco"
    endpoint = $endpoint
    payload  = @{
        user_id = "string_user_id_sample"
        amount  = 10.5
    }
}
$driftBody = $driftObj | ConvertTo-Json
$driftResp = Invoke-RestMethod -Uri "http://localhost:8000/api/ingest" -Method Post -Headers $headers -Body $driftBody -ContentType "application/json"

if ($driftResp.changes_detected -ge 1) {
    Write-Host "PASS: Smoke test passed! Drift detected successfully (changes_detected: $($driftResp.changes_detected))."
    exit 0
} else {
    Write-Host "FAIL: Expected at least 1 change detected, but received $($driftResp.changes_detected)"
    exit 1
}
