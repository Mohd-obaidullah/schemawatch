# setup.ps1 - Automated, safe first-time environment setup for Windows PowerShell 5.1+
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$envExample = Join-Path $root ".env.example"
$envFile = Join-Path $root ".env"

if (-not (Test-Path $envExample)) {
    Write-Error "ERROR: .env.example not found in $root"
    exit 1
}

if (Test-Path $envFile) {
    Write-Host ".env already exists. Preserving existing configuration."
} else {
    # Generate cryptographically secure 256-bit token
    $token = $null
    try {
        $pyToken = python -c "import secrets; print(secrets.token_urlsafe(32))" 2>$null
        if ($pyToken -and $pyToken.Trim().Length -ge 32) {
            $token = $pyToken.Trim()
        }
    } catch {
        # Fall back to .NET RNG if python is not immediately available
    }

    if (-not $token) {
        $bytes = New-Object byte[] 32
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        $rng.GetBytes($bytes)
        $token = [System.Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_').TrimEnd('=')
    }

    # Read .env.example lines and replace token and dev mode
    $lines = Get-Content -Path $envExample
    $newLines = @()
    foreach ($line in $lines) {
        if ($line -match '^SCHEMAWATCH_API_TOKEN=') {
            $newLines += "SCHEMAWATCH_API_TOKEN=$token"
        } elseif ($line -match '^SCHEMAWATCH_DEV_MODE=') {
            $newLines += "SCHEMAWATCH_DEV_MODE=false"
        } else {
            $newLines += $line
        }
    }

    # Write without BOM using ASCII/UTF8 encoding (prevents Docker env_file parsing issues)
    [System.IO.File]::WriteAllLines($envFile, $newLines, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Token saved to .env"
}

Write-Host ""
Write-Host "Next command to run:"
Write-Host "  docker compose up --build -d"
Write-Host "  .\scripts\smoke-test.ps1"
