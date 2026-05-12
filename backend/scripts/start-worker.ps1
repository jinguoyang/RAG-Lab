param()

$ErrorActionPreference = "Stop"

$BackendRoot = Split-Path -Parent $PSScriptRoot
$EnvName = "rag-lab"

Set-Location $BackendRoot
. "$PSScriptRoot\load-env.ps1" -Path (Join-Path $BackendRoot ".env")

# Resolve the real conda.exe and bypass the broken PowerShell conda wrapper.
function Get-CondaExecutable {
    if ($env:CONDA_EXE -and (Test-Path -LiteralPath $env:CONDA_EXE)) {
        return $env:CONDA_EXE
    }

    $fallbackPaths = @(
        "C:\ProgramData\anaconda3\Scripts\conda.exe",
        "C:\ProgramData\miniconda3\Scripts\conda.exe"
    )

    foreach ($path in $fallbackPaths) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }

    throw "Unable to find conda.exe. Please verify that Conda is installed."
}

$CondaExe = Get-CondaExecutable

# Windows 本地 worker 使用 solo pool；通过 python -m celery 避免 console script 入口缺失。
& $CondaExe run --no-capture-output -n $EnvName python -m celery -A app.worker worker --loglevel=info --pool=solo
