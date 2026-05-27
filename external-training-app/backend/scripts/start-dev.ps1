param(
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"

$BackendRoot = Split-Path -Parent $PSScriptRoot

Set-Location $BackendRoot

$EnvFile = Join-Path $BackendRoot ".env"
if (Test-Path -LiteralPath $EnvFile) {
    . "$PSScriptRoot\load-env.ps1" -Path $EnvFile
}

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
