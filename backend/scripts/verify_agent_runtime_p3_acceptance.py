"""Agent Runtime P3 三阶段统一验收脚本。

覆盖 P1 基座、P2 课堂 Graph、P3 内部客服 Graph 的全部门禁检查。
输出 JSON 报告，不输出 API Key。

用法:
    python backend/scripts/verify_agent_runtime_p3_acceptance.py
    python backend/scripts/verify_agent_runtime_p3_acceptance.py --skip-provider
    python backend/scripts/verify_agent_runtime_p3_acceptance.py --allow-skips
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import subprocess
import sys
import time

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 使用当前 Python 解释器，确保子进程使用相同的环境
PYTHON = sys.executable


def _run(cmd: list[str], *, timeout: int = 300, cwd: Path | None = None) -> dict:
    """运行子进程。"""
    try:
        start = time.monotonic()
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(cwd or ROOT_DIR),
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "elapsedMs": elapsed_ms}
    except subprocess.TimeoutExpired:
        return {"exitCode": -1, "stdout": "", "stderr": "TIMEOUT", "elapsedMs": timeout * 1000}
    except Exception as exc:
        return {"exitCode": -1, "stdout": "", "stderr": str(exc), "elapsedMs": 0}


def _run_backend(cmd: list[str], *, timeout: int = 300) -> dict:
    """从 backend 目录执行依赖 .env 的脚本。"""
    return _run(cmd, timeout=timeout, cwd=BACKEND_DIR)


# ---------------------------------------------------------------------------
# P1: 基座检查
# ---------------------------------------------------------------------------

def check_compile() -> dict:
    """编译检查。"""
    proc = _run([PYTHON, "-m", "compileall", "backend/app", "backend/scripts", "-q"])
    return {"name": "compileCheck", "status": "PASS" if proc["exitCode"] == 0 else "FAIL", "elapsedMs": proc["elapsedMs"]}


def check_p1_unit_tests() -> dict:
    """P1 基座单元测试。"""
    files = [
        "backend/app/tests/unit/test_agent_runtime_model_adapter.py",
        "backend/app/tests/unit/test_agent_runtime_checkpoint_service.py",
        "backend/app/tests/unit/test_agent_runtime_memory_service.py",
        "backend/app/tests/unit/test_agent_runtime_qa_run_tool.py",
        "backend/app/tests/unit/test_agent_runtime_rag_agent_factory.py",
        "backend/app/tests/unit/test_agent_runtime_facade.py",
        "backend/app/tests/unit/test_agent_runtime_provider_probe.py",
        "backend/app/tests/unit/test_agent_runtime_scripts.py",
    ]
    proc = _run([PYTHON, "-m", "pytest", "-q", "--tb=short"] + files)
    summary = proc["stdout"].strip().split("\n")[-1] if proc["stdout"] else ""
    return {"name": "p1UnitTests", "status": "PASS" if proc["exitCode"] == 0 else "FAIL", "summary": summary, "elapsedMs": proc["elapsedMs"]}


def check_postgres_checkpoint() -> dict:
    """PostgreSQL Checkpoint 集成测试。"""
    proc = _run([PYTHON, "-m", "pytest", "-q", "-rs", "backend/app/tests/integration/test_agent_runtime_checkpoint_postgres.py"])
    stdout = proc["stdout"]
    if "SKIP" in stdout and "skipped" in stdout:
        return {"name": "postgresCheckpoint", "status": "SKIP", "summary": stdout.strip().split("\n")[-1]}
    if proc["exitCode"] == 0 and "passed" in stdout:
        return {"name": "postgresCheckpoint", "status": "PASS", "summary": stdout.strip().split("\n")[-1], "elapsedMs": proc["elapsedMs"]}
    return {"name": "postgresCheckpoint", "status": "FAIL", "summary": stdout.strip().split("\n")[-1] if stdout else ""}


# ---------------------------------------------------------------------------
# P2: 课堂 Graph 检查
# ---------------------------------------------------------------------------

def check_p2_classroom_tests() -> dict:
    """P2 课堂 Graph 单元和集成测试。"""
    files = [
        "backend/app/tests/unit/test_employee_training_intent.py",
        "backend/app/tests/unit/test_employee_training_graph_routing.py",
        "backend/app/tests/integration/test_employee_training_graph_orchestration.py",
    ]
    proc = _run([PYTHON, "-m", "pytest", "-q", "--tb=short"] + files)
    summary = proc["stdout"].strip().split("\n")[-1] if proc["stdout"] else ""
    return {"name": "p2ClassroomTests", "status": "PASS" if proc["exitCode"] == 0 else "FAIL", "summary": summary, "elapsedMs": proc["elapsedMs"]}


def check_p2_classroom_no_dead_code() -> dict:
    """验证 submit_classroom_event 函数在 return 后无不可达代码。"""
    source = (BACKEND_DIR / "app" / "services" / "training_classroom_service.py").read_text(encoding="utf-8")
    lines = source.split("\n")
    # 找到 submit_classroom_event 函数的 def 行
    func_start = None
    for i, line in enumerate(lines):
        if "def submit_classroom_event(" in line:
            func_start = i
            break
    if func_start is None:
        return {"name": "p2NoDeadCode", "status": "FAIL", "detail": "未找到 submit_classroom_event 函数"}

    # 找到函数体最后一个 return 语句（在顶层缩进 4 空格）
    last_return = None
    for i in range(func_start + 1, len(lines)):
        line = lines[i]
        # 遇到下一个顶层函数定义时停止
        if line.startswith("def ") or line.startswith("class "):
            break
        if line.startswith("    return ") and not line.startswith("        "):
            last_return = i

    if last_return is None:
        return {"name": "p2NoDeadCode", "status": "PASS", "detail": "函数无顶层 return（可能由其他路径结束）"}

    # 跳过多行 return 语句的续行（缩进 > 4 空格或以 ) 开头）
    end_of_return = last_return
    for i in range(last_return + 1, len(lines)):
        line = lines[i]
        if line.startswith("def ") or line.startswith("class "):
            break
        # 续行特征：缩进 > 4 空格，或是闭合括号
        if line.startswith("        ") or line.strip().startswith(")") or line.strip() == "":
            end_of_return = i
            if line.strip().startswith(")") and not line.strip().endswith(","):
                break
        else:
            break

    # 检查 return 结束后是否有非空、非注释的代码
    dead_lines = 0
    for i in range(end_of_return + 1, len(lines)):
        line = lines[i]
        if line.startswith("def ") or line.startswith("class "):
            break
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            dead_lines += 1

    return {
        "name": "p2NoDeadCode",
        "status": "PASS" if dead_lines == 0 else "FAIL",
        "detail": f"发现 {dead_lines} 行不可达代码" if dead_lines > 0 else "无不可达代码",
    }


# ---------------------------------------------------------------------------
# P3: 内部客服 Graph 检查
# ---------------------------------------------------------------------------

def check_p3_customer_service_tests() -> dict:
    """P3 内部客服 Graph 单元和集成测试。"""
    files = [
        "backend/app/tests/unit/test_internal_customer_service_graph.py",
        "backend/app/tests/integration/test_internal_customer_service_runtime.py",
        "backend/app/tests/integration/test_internal_customer_service_memory.py",
    ]
    proc = _run([PYTHON, "-m", "pytest", "-q", "--tb=short"] + files)
    summary = proc["stdout"].strip().split("\n")[-1] if proc["stdout"] else ""
    return {"name": "p3CustomerServiceTests", "status": "PASS" if proc["exitCode"] == 0 else "FAIL", "summary": summary, "elapsedMs": proc["elapsedMs"]}


def check_p3_no_training_dependency() -> dict:
    """验证客服 Graph 不依赖课堂模块。"""
    import importlib
    try:
        mod = importlib.import_module("app.services.agent_runtime.graphs.internal_customer_service_graph")
        import inspect
        source = inspect.getsource(mod)
        has_training = any(kw in source for kw in ["training_classroom_service", "training_progress_service", "training_question"])
        return {
            "name": "p3NoTrainingDependency",
            "status": "FAIL" if has_training else "PASS",
            "detail": "发现课堂依赖" if has_training else "无课堂依赖",
        }
    except ImportError as exc:
        return {"name": "p3NoTrainingDependency", "status": "SKIP", "detail": f"依赖缺失: {exc}"}
    except Exception as exc:
        return {"name": "p3NoTrainingDependency", "status": "FAIL", "detail": str(exc)}


def check_p3_scenario_registry() -> dict:
    """验证 knowledge_qa 场景已注册。"""
    try:
        from app.services.agent_runtime.scenario_registry import get_scenario_registry
        registry = get_scenario_registry()
        builder = registry.get("knowledge_qa")
        return {
            "name": "p3ScenarioRegistry",
            "status": "PASS" if builder is not None else "FAIL",
            "detail": "knowledge_qa 已注册" if builder is not None else "knowledge_qa 未注册",
        }
    except ImportError as exc:
        return {"name": "p3ScenarioRegistry", "status": "SKIP", "detail": f"依赖缺失: {exc}"}
    except Exception as exc:
        return {"name": "p3ScenarioRegistry", "status": "FAIL", "detail": str(exc)}


def check_cross_app_isolation() -> dict:
    """验证跨 App 会话隔离测试。"""
    proc = _run([PYTHON, "-m", "pytest", "-q", "--tb=short", "backend/app/tests/unit/test_app_runtime_protection.py::test_conversation_cannot_cross_app"])
    return {"name": "crossAppIsolation", "status": "PASS" if proc["exitCode"] == 0 else "FAIL", "elapsedMs": proc["elapsedMs"]}


# ---------------------------------------------------------------------------
# 全量回归
# ---------------------------------------------------------------------------

def check_full_regression() -> dict:
    """运行完整后端测试套件。"""
    proc = _run([PYTHON, "-m", "pytest", "backend/app/tests/unit/", "backend/app/tests/integration/", "-q", "--tb=line"], timeout=600)
    summary = proc["stdout"].strip().split("\n")[-1] if proc["stdout"] else ""
    return {"name": "fullRegression", "status": "PASS" if proc["exitCode"] == 0 else "FAIL", "summary": summary, "elapsedMs": proc["elapsedMs"]}


# ---------------------------------------------------------------------------
# Provider 探测
# ---------------------------------------------------------------------------

def check_provider_probe(*, skip: bool = False) -> dict:
    """真实 Provider 能力探测。"""
    if skip:
        return {"name": "providerProbe", "status": "NOT_RUN", "detail": "使用 --skip-provider 跳过"}
    proc = _run_backend([PYTHON, "scripts/verify_agent_runtime_provider.py"])
    return {
        "name": "providerProbe",
        "status": "PASS" if proc["exitCode"] == 0 else "FAIL",
        "detail": proc["stdout"] if proc["exitCode"] == 0 else (proc["stderr"] or proc["stdout"]),
        "elapsedMs": proc["elapsedMs"],
    }


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Runtime P3 三阶段验收")
    parser.add_argument("--skip-provider", action="store_true", help="跳过真实 Provider 探测")
    parser.add_argument("--allow-skips", action="store_true", help="SKIP 和 NOT_RUN 不阻断退出码")
    args = parser.parse_args()

    checks = [
        check_compile(),
        check_p1_unit_tests(),
        check_postgres_checkpoint(),
        check_p2_classroom_tests(),
        check_p2_classroom_no_dead_code(),
        check_p3_customer_service_tests(),
        check_p3_no_training_dependency(),
        check_p3_scenario_registry(),
        check_cross_app_isolation(),
        check_full_regression(),
        check_provider_probe(skip=args.skip_provider),
    ]

    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    skipped = sum(1 for c in checks if c["status"] in {"SKIP", "NOT_RUN"})

    report = {
        "stage": "P3",
        "title": "Agent Runtime 三阶段统一验收",
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": len(checks),
        "checks": checks,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

    # 退出码：FAIL 始终阻断；SKIP/NOT_RUN 按 --allow-skips 决定
    if failed > 0:
        sys.exit(1)
    if skipped > 0 and not args.allow_skips:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
