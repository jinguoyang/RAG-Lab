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

python "$PSScriptRoot\ensure_database.py"
alembic upgrade $Revision
