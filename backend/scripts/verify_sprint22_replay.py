"""验证 Sprint 22 真实回放、复跑与对比链路。

脚本采用源码级护栏检查，避免本地必须常驻真实向量库、搜索、图数据库和 LLM 服务。
真实环境可在此基础上追加端到端网络复测；这里确保代码契约已经覆盖回放上下文、复跑关系、结果对比和权限边界。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    """按 UTF-8 读取仓库文件，避免中文注释和验收提示乱码。"""
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    """用明确错误说明指出 Sprint 22 未完成项。"""
    if not condition:
        raise AssertionError(message)


def _assert_contains(source: str, needle: str, message: str) -> None:
    """校验关键实现片段存在，避免验收脚本被环境依赖阻塞。"""
    _assert(needle in source, message)


def verify_replay_context_snapshot() -> None:
    """校验回放上下文包含复跑所需配置、检索通道和原诊断摘要。"""
    schema_source = _read("app/schemas/qa_run.py")
    service_source = _read("app/services/qa_run_service.py")
    frontend_types = (ROOT.parent / "frontend/src/app/types/qaRun.ts").read_text(encoding="utf-8")

    for field in [
        "retrievalChannels",
        "retrievalTopK",
        "temperature",
        "maxContextTokens",
        "graphSnapshotId",
        "providerDiagnostics",
    ]:
        _assert_contains(schema_source, field, f"QARunReplayContextDTO 缺少字段: {field}")
        _assert_contains(frontend_types, field, f"前端 QARunReplayContextDTO 缺少字段: {field}")

    _assert_contains(service_source, "_build_replay_context_snapshot(", "缺少回放上下文快照构建函数")
    _assert_contains(service_source, '"pipelineParams"', "回放上下文未复用原运行 pipelineParams")
    _assert_contains(service_source, '"providerErrors"', "回放上下文未暴露 Provider 诊断摘要")


def verify_replay_compare_api() -> None:
    """校验后端提供来源 run 与复跑 run 的轻量对比接口。"""
    schema_source = _read("app/schemas/qa_run.py")
    route_source = _read("app/api/routes/qa_runs.py")
    service_source = _read("app/services/qa_run_service.py")

    for name in [
        "QARunCompareDTO",
        "QARunCompareSummaryDTO",
        "QARunCompareEvidenceDeltaDTO",
        "QARunCompareTraceDeltaDTO",
    ]:
        _assert_contains(schema_source, name, f"缺少对比 DTO: {name}")

    _assert_contains(route_source, "/{run_id}/compare/{target_run_id}", "缺少 QARun 对比 API 路由")
    _assert_contains(service_source, "def compare_qa_runs(", "缺少 QARun 对比服务函数")
    _assert_contains(service_source, "qa_run_trace_steps.c.started_at", "Trace 对比未读取步骤开始时间")
    _assert_contains(service_source, "qa_run_trace_steps.c.ended_at", "Trace 对比未读取步骤结束时间")
    for field in ["answerChanged", "evidenceDelta", "citationDelta", "traceDelta", "configDiff"]:
        _assert_contains(service_source, field, f"对比结果缺少字段: {field}")


def verify_replay_permissions() -> None:
    """校验回放和对比不绕过当前用户的历史读取与运行权限。"""
    service_source = _read("app/services/qa_run_service.py")

    _assert_contains(service_source, '_require_permission(session, current_user, kb_id, "kb.qa.run")', "回放上下文缺少运行权限校验")
    _assert_contains(service_source, '_read_visible_qa_run(session, current_user, kb_id, request.sourceRunId)', "创建复跑时未校验来源 run 可见性")
    _assert_contains(service_source, '_require_permission(session, current_user, kb_id, "kb.qa.history.read")', "对比接口缺少历史读取权限校验")
    _assert_contains(service_source, "redactionStatus=\"redacted\"", "历史 Evidence 二次读取缺少脱敏返回路径")


def verify_frontend_replay_compare() -> None:
    """校验 P09/P10 已接入复跑来源和结果对比展示。"""
    p09_source = (ROOT.parent / "frontend/src/app/pages/P09_QADebug.tsx").read_text(encoding="utf-8")
    p10_source = (ROOT.parent / "frontend/src/app/pages/P10_QAHistory.tsx").read_text(encoding="utf-8")
    service_source = (ROOT.parent / "frontend/src/app/services/qaRunService.ts").read_text(encoding="utf-8")

    _assert_contains(p09_source, "sourceRunId", "P09 创建复跑时未保留 sourceRunId")
    _assert_contains(p09_source, "providerDiagnostics", "P09 未展示回放诊断摘要")
    _assert_contains(service_source, "fetchQARunCompare", "前端缺少 QARun 对比 API 调用")
    _assert_contains(p10_source, "fetchQARunCompare", "P10 未接入 QARun 对比接口")
    _assert_contains(p10_source, "回放对比", "P10 未展示回放对比区域")
    _assert_contains(p10_source, "sourceRunId", "P10 未识别复跑来源关系")


def main() -> None:
    """执行 Sprint 22 源码级验收。"""
    verify_replay_context_snapshot()
    verify_replay_compare_api()
    verify_replay_permissions()
    verify_frontend_replay_compare()
    print("Sprint 22 replay verification passed.")


if __name__ == "__main__":
    main()
