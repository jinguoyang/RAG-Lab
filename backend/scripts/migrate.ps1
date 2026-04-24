Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $backendRoot

# 迁移命令统一走 Conda 环境，避免本机全局 Python 依赖污染执行结果。
conda run -n rag-lab python -m alembic upgrade head
