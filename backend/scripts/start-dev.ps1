param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$BackendRoot = Split-Path -Parent $PSScriptRoot
$EnvName = "rag-lab"

Set-Location $BackendRoot

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

# Start with the project-specific Conda env to avoid using base by mistake.
& $CondaExe run -n $EnvName python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
