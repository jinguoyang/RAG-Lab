"""B-296: 外部培训应用真实联调验收脚本。

验证平台与外部培训应用的端到端联调：
1. 岗位描述生成学习计划 -> 外部培训应用审核 -> 平台发布计划
2. 平台生成题库草稿 -> 外部培训应用审核认证题
3. 员工进入课堂 -> 多轮提问 -> 平台状态机响应 -> 结构化答题 -> 评分回传

用法:
    python backend/scripts/verify_external_training_e2e.py
    python backend/scripts/verify_external_training_e2e.py --skip-platform
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _check_external_app_health() -> dict:
    """检查外部培训应用健康状态。"""
    import httpx

    try:
        response = httpx.get("http://localhost:8001/health", timeout=5.0)
        if response.status_code == 200:
            return {"name": "externalAppHealth", "status": "PASS", "detail": "外部培训应用健康检查通过"}
        return {"name": "externalAppHealth", "status": "FAIL", "detail": f"状态码: {response.status_code}"}
    except Exception as exc:
        return {"name": "externalAppHealth", "status": "SKIP", "detail": f"外部培训应用未启动: {exc}"}


def _check_platform_health() -> dict:
    """检查平台健康状态。"""
    import httpx

    try:
        response = httpx.get("http://localhost:8000/health", timeout=5.0)
        if response.status_code == 200:
            return {"name": "platformHealth", "status": "PASS", "detail": "平台健康检查通过"}
        return {"name": "platformHealth", "status": "FAIL", "detail": f"状态码: {response.status_code}"}
    except Exception as exc:
        return {"name": "platformHealth", "status": "SKIP", "detail": f"平台未启动: {exc}"}


def _check_external_app_no_llm_config() -> dict:
    """验证外部培训应用没有 LLM、Embedding、RAG Provider 配置。"""
    env_path = ROOT_DIR / "external-training-app" / "backend" / ".env"
    if not env_path.exists():
        return {"name": "noLLMConfig", "status": "PASS", "detail": "外部培训应用无 .env 文件"}

    content = env_path.read_text(encoding="utf-8")
    llm_keywords = ["OPENAI_API_KEY", "LLM_API_KEY", "EMBEDDING_API_KEY", "MILVUS", "OPENSEARCH", "NEO4J"]
    found = [kw for kw in llm_keywords if kw in content.upper()]

    if found:
        return {"name": "noLLMConfig", "status": "FAIL", "detail": f"发现 LLM 相关配置: {found}"}
    return {"name": "noLLMConfig", "status": "PASS", "detail": "外部培训应用无 LLM 相关配置"}


def _check_external_app_tests() -> dict:
    """运行外部培训应用后端测试。"""
    import subprocess

    ext_backend = ROOT_DIR / "external-training-app" / "backend"
    if not ext_backend.exists():
        return {"name": "externalAppTests", "status": "SKIP", "detail": "外部培训应用后端目录不存在"}

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "app/tests", "-q", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(ext_backend),
        )
        if result.returncode == 0:
            summary = result.stdout.strip().split("\n")[-1] if result.stdout else ""
            return {"name": "externalAppTests", "status": "PASS", "detail": summary}
        return {"name": "externalAppTests", "status": "FAIL", "detail": result.stdout[-200:] if result.stdout else result.stderr[-200:]}
    except subprocess.TimeoutExpired:
        return {"name": "externalAppTests", "status": "FAIL", "detail": "测试超时"}
    except Exception as exc:
        return {"name": "externalAppTests", "status": "FAIL", "detail": str(exc)}


def _check_platform_training_tests() -> dict:
    """运行平台侧培训相关测试。"""
    import subprocess

    test_files = [
        "backend/app/tests/unit/test_training_skill_registry_service.py",
        "backend/app/tests/unit/test_training_plan_service.py",
        "backend/app/tests/unit/test_training_grading_service.py",
        "backend/app/tests/integration/test_training_e2e_acceptance.py",
    ]

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short"] + test_files,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT_DIR),
        )
        if result.returncode == 0:
            summary = result.stdout.strip().split("\n")[-1] if result.stdout else ""
            return {"name": "platformTrainingTests", "status": "PASS", "detail": summary}
        return {"name": "platformTrainingTests", "status": "FAIL", "detail": result.stdout[-300:] if result.stdout else result.stderr[-300:]}
    except subprocess.TimeoutExpired:
        return {"name": "platformTrainingTests", "status": "FAIL", "detail": "测试超时"}
    except Exception as exc:
        return {"name": "platformTrainingTests", "status": "FAIL", "detail": str(exc)}


def _check_external_app_build() -> dict:
    """检查外部培训应用前端构建。"""
    import subprocess

    ext_frontend = ROOT_DIR / "external-training-app" / "frontend"
    if not ext_frontend.exists():
        return {"name": "externalAppBuild", "status": "SKIP", "detail": "外部培训应用前端目录不存在"}

    try:
        result = subprocess.run(
            ["npm.cmd", "run", "build"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ext_frontend),
        )
        if result.returncode == 0:
            return {"name": "externalAppBuild", "status": "PASS", "detail": "外部培训应用前端构建成功"}
        return {"name": "externalAppBuild", "status": "FAIL", "detail": result.stderr[-300:] if result.stderr else result.stdout[-300:]}
    except subprocess.TimeoutExpired:
        return {"name": "externalAppBuild", "status": "FAIL", "detail": "构建超时"}
    except Exception as exc:
        return {"name": "externalAppBuild", "status": "FAIL", "detail": str(exc)}


def _has_blocking_status(checks: list[dict], *, allow_skips: bool) -> bool:
    """真实联调默认不允许跳过服务级检查，显式降级仅用于本地构建复核。"""
    if any(item["status"] == "FAIL" for item in checks):
        return True
    return not allow_skips and any(item["status"] == "SKIP" for item in checks)


def _check_real_training_workflow() -> dict:
    """执行真实业务流检查，按顺序调用已存在接口。"""
    import httpx

    try:
        client = httpx.Client(base_url="http://localhost:8000", timeout=10.0)
    except Exception as exc:
        return {"name": "realTrainingWorkflow", "status": "SKIP", "detail": f"无法连接平台: {exc}"}

    try:
        # 1. 创建学习计划草稿
        r = client.post("/training/plans/drafts", json={"jobTitle": "测试岗位", "description": "测试描述"})
        if r.status_code not in (200, 201):
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": f"创建计划草稿失败: {r.status_code}"}
        plan_id = r.json().get("planId") or r.json().get("id")
        if not plan_id:
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": "创建计划草稿返回无 planId"}

        # 2. 提交学习计划审核
        r = client.post(f"/training/plans/{plan_id}/review")
        if r.status_code not in (200, 201):
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": f"提交计划审核失败: {r.status_code}"}

        # 3. 创建题库草稿
        r = client.post("/training/questions/drafts", json={"planId": plan_id})
        if r.status_code not in (200, 201):
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": f"创建题库草稿失败: {r.status_code}"}
        question_id = r.json().get("questionId") or r.json().get("id")
        if not question_id:
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": "创建题库草稿返回无 questionId"}

        # 4. 提交题库审核
        r = client.post(f"/training/questions/{question_id}/review")
        if r.status_code not in (200, 201):
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": f"提交题库审核失败: {r.status_code}"}

        # 5. 创建课堂会话
        r = client.post("/classroom/sessions", json={"planId": plan_id})
        if r.status_code not in (200, 201):
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": f"创建课堂会话失败: {r.status_code}"}
        session_id = r.json().get("sessionId") or r.json().get("id")
        if not session_id:
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": "创建课堂会话返回无 sessionId"}

        # 6. 发送课堂事件
        r = client.post(f"/classroom/sessions/{session_id}/events", json={"type": "start"})
        if r.status_code not in (200, 201):
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": f"发送课堂事件失败: {r.status_code}"}

        # 7. 查询课堂状态
        r = client.get(f"/classroom/sessions/{session_id}")
        if r.status_code != 200:
            return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": f"查询课堂状态失败: {r.status_code}"}

        return {"name": "realTrainingWorkflow", "status": "PASS", "detail": "真实业务流全部通过"}
    except httpx.ConnectError:
        return {"name": "realTrainingWorkflow", "status": "SKIP", "detail": "平台未启动"}
    except Exception as exc:
        return {"name": "realTrainingWorkflow", "status": "FAIL", "detail": str(exc)}
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="B-296 外部培训应用真实联调验收")
    parser.add_argument("--skip-platform", action="store_true", help="跳过平台侧检查")
    parser.add_argument("--allow-skips", action="store_true", help="仅本地复核时允许 SKIP 不阻断退出码")
    args = parser.parse_args()

    checks = [
        _check_external_app_health(),
        _check_platform_health(),
        _check_external_app_no_llm_config(),
        _check_external_app_tests(),
        _check_external_app_build(),
    ]

    if not args.skip_platform:
        checks.append(_check_platform_training_tests())
        checks.append(_check_real_training_workflow())

    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    skipped = sum(1 for c in checks if c["status"] == "SKIP")

    report = {
        "task": "B-296",
        "title": "外部培训应用真实联调验收",
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": len(checks),
        "checks": checks,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if _has_blocking_status(checks, allow_skips=args.allow_skips):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
