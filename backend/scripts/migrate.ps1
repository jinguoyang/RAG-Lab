Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot

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

$condaExe = Get-CondaExecutable

# Run migrations in the project Conda env to avoid using a global Python.
& $condaExe run -n rag-lab python -m alembic upgrade head
