"""Agent Runtime P1 统一验收脚本。

执行全部门禁检查，输出 JSON 报告。
默认：SKIP 和 NOT_RUN 视为阻断（非零退出）。使用 --allow-skips 显式降级。

用法:
    python backend/scripts/verify_agent_runtime_foundation.py
    python backend/scripts/verify_agent_runtime_foundation.py --skip-provider
    python backend/scripts/verify_agent_runtime_foundation.py --allow-skips
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

PYTHON = sys.executable


def _run(cmd: list[str], *, env: dict | None = None, timeout: int = 120) -> dict:
    """运行子进程，cwd 固定为 BACKEND_DIR，确保 .env 加载口径一致。"""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(BACKEND_DIR), env=env,
        )
        return {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"exitCode": -1, "stdout": "", "stderr": "TIMEOUT"}
    except Exception as exc:
        return {"exitCode": -1, "stdout": "", "stderr": str(exc)}


def _run_root(cmd: list[str], *, env: dict | None = None, timeout: int = 120) -> dict:
    """运行子进程，cwd 固定为仓库根目录（pytest 需要从根目录运行）。"""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT_DIR), env=env,
        )
        return {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"exitCode": -1, "stdout": "", "stderr": "TIMEOUT"}
    except Exception as exc:
        return {"exitCode": -1, "stdout": "", "stderr": str(exc)}


def check_compile() -> dict:
    """编译检查。"""
    proc = _run_root([PYTHON, "-m", "compileall", "backend/app", "backend/scripts", "-q"])
    return {
        "name": "compileCheck",
        "status": "PASS" if proc["exitCode"] == 0 else "FAIL",
        "detail": proc["stderr"] if proc["exitCode"] != 0 else "",
    }


def check_unit_tests() -> dict:
    """运行全部 P1 单元测试。"""
    test_files = [
        "backend/app/tests/unit/test_agent_runtime_model_adapter.py",
        "backend/app/tests/unit/test_agent_runtime_checkpoint_service.py",
        "backend/app/tests/unit/test_agent_runtime_memory_service.py",
        "backend/app/tests/unit/test_agent_runtime_qa_run_tool.py",
        "backend/app/tests/unit/test_agent_runtime_rag_agent_factory.py",
        "backend/app/tests/unit/test_agent_runtime_skill_adapter.py",
        "backend/app/tests/unit/test_agent_runtime_facade.py",
        "backend/app/tests/unit/test_agent_runtime_provider_probe.py",
        "backend/app/tests/unit/test_agent_runtime_scripts.py",
    ]
    proc = _run_root([PYTHON, "-m", "pytest", "-q", "--tb=short"] + test_files)
    summary = proc["stdout"].strip().split("\n")[-1] if proc["stdout"] else ""
    return {
        "name": "unitTests",
        "status": "PASS" if proc["exitCode"] == 0 else "FAIL",
        "summary": summary,
        "detail": proc["stderr"] if proc["exitCode"] != 0 else "",
    }


def check_regression_tests() -> dict:
    """运行关键历史回归测试。"""
    test_files = [
        "backend/app/tests/unit/test_qa_providers.py",
        "backend/app/tests/unit/test_app_runtime_protection.py",
        "backend/app/tests/unit/test_app_runtime_embed_token.py",
        "backend/app/tests/integration/test_employee_training_agent_runtime.py",
        "backend/app/tests/integration/test_training_e2e_acceptance.py",
    ]
    proc = _run_root([PYTHON, "-m", "pytest", "-q", "--tb=short"] + test_files)
    summary = proc["stdout"].strip().split("\n")[-1] if proc["stdout"] else ""
    return {
        "name": "regressionTests",
        "status": "PASS" if proc["exitCode"] == 0 else "FAIL",
        "summary": summary,
        "detail": proc["stderr"] if proc["exitCode"] != 0 else "",
    }


def check_script_entrypoints() -> dict:
    """验证两个脚本 --help 不执行副作用且退出码 0。"""
    results = []
    for script in [
        "backend/scripts/setup_langgraph_checkpoints.py",
        "backend/scripts/verify_agent_runtime_provider.py",
    ]:
        proc = _run_root([PYTHON, script, "--help"])
        ok = proc["exitCode"] == 0 and "ModuleNotFoundError" not in proc["stderr"]
        results.append({"script": script, "ok": ok, "exitCode": proc["exitCode"]})
    all_ok = all(r["ok"] for r in results)
    return {
        "name": "scriptEntrypoints",
        "status": "PASS" if all_ok else "FAIL",
        "detail": results,
    }


def check_postgres_checkpoint() -> dict:
    """检查 PostgreSQL Checkpointer 集成测试状态。"""
    proc = _run_root([
        PYTHON, "-m", "pytest", "-q", "-rs",
        "backend/app/tests/integration/test_agent_runtime_checkpoint_postgres.py",
    ])
    stdout = proc["stdout"]
    if "SKIP" in stdout and "skipped" in stdout:
        return {
            "name": "postgresCheckpoint",
            "status": "SKIP",
            "summary": stdout.strip().split("\n")[-1],
            "detail": "需要设置 RAG_LAB_TEST_POSTGRES_URL 环境变量",
        }
    if proc["exitCode"] == 0 and "passed" in stdout:
        return {
            "name": "postgresCheckpoint",
            "status": "PASS",
            "summary": stdout.strip().split("\n")[-1],
        }
    return {
        "name": "postgresCheckpoint",
        "status": "FAIL",
        "summary": stdout.strip().split("\n")[-1] if stdout else "",
        "detail": proc["stderr"],
    }


def check_provider_probe(*, skip: bool = False) -> dict:
    """检查 Provider 探测；配置缺失时诚实标记 NOT_RUN。"""
    if skip:
        return {
            "name": "providerProbe",
            "status": "NOT_RUN",
            "detail": "使用 --skip-provider 跳过",
        }

    # 先用 dry-run 检查配置，再从 backend/ 目录执行真实 Provider 网络探测。
    proc = _run([PYTHON, "scripts/verify_agent_runtime_provider.py", "--dry-run"])
    if proc["exitCode"] != 0:
        return {
            "name": "providerProbe",
            "status": "FAIL",
            "detail": proc["stderr"] or proc["stdout"],
        }

    try:
        start = proc["stdout"].index("{")
        config = json.loads(proc["stdout"][start:])
    except (ValueError, json.JSONDecodeError):
        return {
            "name": "providerProbe",
            "status": "FAIL",
            "detail": f"无法解析 Provider dry-run 输出：{proc['stdout']}",
        }

    if not config.get("endpoint") or not config.get("apiKey"):
        return {
            "name": "providerProbe",
            "status": "NOT_RUN",
            "detail": "未配置 RAG_LAB_LLM_ENDPOINT 或 RAG_LAB_LLM_API_KEY，未执行真实 Provider 网络探测。",
        }

    proc = _run([PYTHON, "scripts/verify_agent_runtime_provider.py"])
    return {
        "name": "providerProbe",
        "status": "PASS" if proc["exitCode"] == 0 else "FAIL",
        "detail": proc["stdout"] if proc["exitCode"] == 0 else (proc["stderr"] or proc["stdout"]),
    }


def check_config_sync() -> dict:
    """检查 .env.example 是否包含全部 agent_runtime 配置。"""
    env_example = BACKEND_DIR / ".env.example"
    content = env_example.read_text(encoding="utf-8")
    required_keys = [
        "RAG_LAB_AGENT_RUNTIME_ENABLED",
        "RAG_LAB_AGENT_RUNTIME_DEFAULT_VERSION",
        "RAG_LAB_AGENT_RUNTIME_CHECKPOINT_BACKEND",
        "RAG_LAB_AGENT_RUNTIME_CHECKPOINT_DATABASE_URL",
        "RAG_LAB_AGENT_RUNTIME_SUMMARY_TRIGGER_TOKENS",
        "RAG_LAB_AGENT_RUNTIME_SUMMARY_KEEP_MESSAGES",
    ]
    missing = [k for k in required_keys if k not in content]
    return {
        "name": "configSync",
        "status": "PASS" if not missing else "FAIL",
        "missing": missing,
    }


def has_blocking_status(report: list[dict], *, allow_skips: bool) -> bool:
    """判断验收报告是否包含阻断状态；显式降级时允许 SKIP 和 NOT_RUN。"""
    if any(item["status"] == "FAIL" for item in report):
        return True
    if allow_skips:
        return False
    return any(item["status"] in {"SKIP", "NOT_RUN"} for item in report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Runtime P1 统一验收")
    parser.add_argument("--skip-provider", action="store_true", help="跳过真实 Provider 探测，标记 NOT_RUN")
    parser.add_argument("--allow-skips", action="store_true", help="SKIP 和 NOT_RUN 不阻断退出码（显式降级）")
    args = parser.parse_args()

    checks = [
        check_compile,
        check_unit_tests,
        check_regression_tests,
        check_script_entrypoints,
        check_postgres_checkpoint,
        lambda: check_provider_probe(skip=args.skip_provider),
        check_config_sync,
    ]

    report = []
    for check_fn in checks:
        name = check_fn.__name__ if hasattr(check_fn, "__name__") else "lambda"
        print(f"Running: {name}...", file=sys.stderr)
        result = check_fn()
        report.append(result)
        status = result["status"]
        icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "○", "NOT_RUN": "—"}.get(status, "?")
        print(f"  {icon} {result['name']}: {status}", file=sys.stderr)

    # 输出 JSON 报告
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    print()

    failed = [r for r in report if r["status"] == "FAIL"]
    skipped = [r for r in report if r["status"] == "SKIP"]
    not_run = [r for r in report if r["status"] == "NOT_RUN"]

    if failed:
        print(f"\n{len(failed)} FAIL, {len(skipped)} SKIP, {len(not_run)} NOT_RUN", file=sys.stderr)
        sys.exit(1)

    if has_blocking_status(report, allow_skips=args.allow_skips):
        print(
            f"\n{len(skipped)} SKIP, {len(not_run)} NOT_RUN — 默认阻断。使用 --allow-skips 显式降级。",
            file=sys.stderr,
        )
        sys.exit(1)

    if skipped:
        print(f"\n{len(skipped)} SKIP (已通过 --allow-skips 降级)", file=sys.stderr)
    if not_run:
        print(f"\n{len(not_run)} NOT_RUN (已通过 --allow-skips 降级)", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
