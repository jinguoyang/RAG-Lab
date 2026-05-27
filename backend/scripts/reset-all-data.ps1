<#
.SYNOPSIS
    清空 RAG-Lab 项目全部数据（PostgreSQL、Milvus、OpenSearch、MinIO、Neo4j、Redis）。
.DESCRIPTION
    加载 .env 配置，调用 reset_all_data.py 执行清空操作。
.PARAMETER DryRun
    仅打印将要执行的操作，不实际执行。
.PARAMETER Yes
    跳过确认提示，直接执行。
#>
param(
    [switch]$DryRun,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

# 定位脚本目录和 .env
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BackendDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $BackendDir ".env"

if (-not (Test-Path $EnvFile)) {
    Write-Error "找不到 .env 文件: $EnvFile"
    exit 1
}

# 构建 Python 参数
$PyArgs = @()
if ($DryRun) { $PyArgs += "--dry-run" }
if ($Yes)    { $PyArgs += "--yes" }

# 加载 conda 环境（如果存在）
$CondaExe = Get-Command conda -ErrorAction SilentlyContinue
if ($CondaExe) {
    $condaHook = & conda shell.powershell hook 2>$null
    if ($condaHook) {
        Invoke-Expression $condaHook
        conda activate rag-lab 2>$null
    }
}

# 执行
$PyScript = Join-Path $ScriptDir "reset_all_data.py"
python $PyScript @PyArgs
