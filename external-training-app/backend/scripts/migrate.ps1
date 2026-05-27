param(
    [string]$Revision = "head"
)

$ErrorActionPreference = "Stop"

$BackendRoot = Split-Path -Parent $PSScriptRoot

Set-Location $BackendRoot

$EnvFile = Join-Path $BackendRoot ".env"
if (Test-Path -LiteralPath $EnvFile) {
    . "$PSScriptRoot\load-env.ps1" -Path $EnvFile
}

alembic upgrade $Revision
