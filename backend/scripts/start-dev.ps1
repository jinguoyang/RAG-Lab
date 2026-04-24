param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$BackendRoot = Split-Path -Parent $PSScriptRoot
$EnvName = "rag-lab"

Set-Location $BackendRoot

# 使用项目专属 Conda 环境启动，避免误用 base 或其他项目环境。
conda run -n $EnvName python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
