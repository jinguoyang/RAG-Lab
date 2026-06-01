"""Agent Runtime: 脚本入口、DSN 转换与 argparse 测试。"""

import subprocess
import sys
from pathlib import Path
import json

PYTHON = sys.executable
# 仓库根目录：无论从哪里运行 pytest，都能正确定位脚本
ROOT_DIR = Path(__file__).resolve().parents[4]
BACKEND_DIR = ROOT_DIR / "backend"


# ---------------------------------------------------------------------------
# 脚本入口点：--help 不执行副作用
# ---------------------------------------------------------------------------


def test_setup_langgraph_checkpoints_help_exits_zero():
    """--help 应退出码 0，不触发数据库操作。"""
    script = str(BACKEND_DIR / "scripts" / "setup_langgraph_checkpoints.py")
    result = subprocess.run(
        [PYTHON, script, "--help"],
        capture_output=True, text=True, cwd=str(BACKEND_DIR),
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "初始化 LangGraph" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr


def test_verify_agent_runtime_provider_help_exits_zero():
    """--help 应退出码 0，不触发 Provider 调用。"""
    script = str(BACKEND_DIR / "scripts" / "verify_agent_runtime_provider.py")
    result = subprocess.run(
        [PYTHON, script, "--help"],
        capture_output=True, text=True, cwd=str(BACKEND_DIR),
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "探测 LLM Provider" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr


def test_setup_langgraph_checkpoints_check_mode_exits_nonzero_without_db():
    """--check 模式在未配置数据库时应退出码非零。"""
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith("RAG_LAB_")}
    env["RAG_LAB_DATABASE_URL"] = ""
    script = str(BACKEND_DIR / "scripts" / "setup_langgraph_checkpoints.py")
    result = subprocess.run(
        [PYTHON, script, "--check"],
        capture_output=True, text=True, cwd=str(BACKEND_DIR), env=env,
    )
    assert result.returncode != 0, "未配置数据库时 --check 应退出码非零"


def test_verify_agent_runtime_provider_dry_run_exits_zero():
    """--dry-run 应退出码 0，不调用 Provider。"""
    script = str(BACKEND_DIR / "scripts" / "verify_agent_runtime_provider.py")
    result = subprocess.run(
        [PYTHON, script, "--dry-run"],
        capture_output=True, text=True, cwd=str(BACKEND_DIR),
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    output = json.loads(result.stdout)
    assert output["dryRun"] is True
    assert "apiKey" in output


# ---------------------------------------------------------------------------
# DSN 转换：直接导入函数，不依赖模块路径前缀
# ---------------------------------------------------------------------------


def _import_to_psycopg_dsn():
    """导入 _to_psycopg_dsn，兼容从仓库根或 backend/ 目录运行。"""
    import importlib
    try:
        mod = importlib.import_module("scripts.setup_langgraph_checkpoints")
    except ModuleNotFoundError:
        mod = importlib.import_module("backend.scripts.setup_langgraph_checkpoints")
    return mod._to_psycopg_dsn


def test_to_psycopg_dsn_converts_sqlalchemy_prefix():
    fn = _import_to_psycopg_dsn()
    assert fn("postgresql+psycopg://user:pass@host/db") == "postgresql://user:pass@host/db"


def test_to_psycopg_dsn_converts_asyncpg_prefix():
    fn = _import_to_psycopg_dsn()
    assert fn("postgresql+asyncpg://user:pass@host/db") == "postgresql://user:pass@host/db"


def test_to_psycopg_dsn_passthrough_plain_postgresql():
    fn = _import_to_psycopg_dsn()
    assert fn("postgresql://user:pass@host/db") == "postgresql://user:pass@host/db"


def test_to_psycopg_dsn_returns_none_for_none():
    fn = _import_to_psycopg_dsn()
    assert fn(None) is None


# ---------------------------------------------------------------------------
# 统一验收门禁：真实探测和默认阻断
# ---------------------------------------------------------------------------


def _import_foundation_verifier():
    """导入统一验收脚本，兼容从仓库根或 backend/ 目录运行。"""
    import importlib
    try:
        return importlib.import_module("scripts.verify_agent_runtime_foundation")
    except ModuleNotFoundError:
        return importlib.import_module("backend.scripts.verify_agent_runtime_foundation")


def test_foundation_verifier_runs_real_provider_probe_when_configured(monkeypatch):
    """Provider 配置存在时，dry-run 之后必须继续执行真实网络探测。"""
    verifier = _import_foundation_verifier()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "--dry-run" in cmd:
            return {
                "exitCode": 0,
                "stdout": '{"dryRun": true, "endpoint": true, "apiKey": true}',
                "stderr": "",
            }
        return {
            "exitCode": 0,
            "stdout": '{"chat": true, "toolCalling": true, "structuredOutput": true, "summarization": true}',
            "stderr": "",
        }

    monkeypatch.setattr(verifier, "_run", fake_run)
    monkeypatch.setattr(verifier, "_run_root", fake_run)

    result = verifier.check_provider_probe()

    assert result["status"] == "PASS"
    assert len(calls) == 2
    assert "--dry-run" in calls[0]
    assert "--dry-run" not in calls[1]


def test_foundation_verifier_marks_provider_not_run_without_config(monkeypatch):
    """缺少 Provider 配置时只能标记 NOT_RUN，不能伪装成 PASS。"""
    verifier = _import_foundation_verifier()

    def fake_run(cmd, **kwargs):
        return {
            "exitCode": 0,
            "stdout": '{"dryRun": true, "endpoint": false, "apiKey": false}',
            "stderr": "",
        }

    monkeypatch.setattr(verifier, "_run", fake_run)
    monkeypatch.setattr(verifier, "_run_root", fake_run)

    result = verifier.check_provider_probe()

    assert result["status"] == "NOT_RUN"


def test_foundation_verifier_blocks_skip_and_not_run_by_default():
    """默认验收必须阻断未执行的关键能力，显式降级时才允许继续。"""
    verifier = _import_foundation_verifier()
    report = [
        {"name": "postgresCheckpoint", "status": "SKIP"},
        {"name": "providerProbe", "status": "NOT_RUN"},
    ]

    assert verifier.has_blocking_status(report, allow_skips=False) is True
    assert verifier.has_blocking_status(report, allow_skips=True) is False
