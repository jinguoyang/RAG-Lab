"""平台 Agent Runtime Facade。

职责：
- 业务服务唯一调用入口。
- 版本路由（Legacy / Shadow / Primary）。
- Graph 执行、Trace 关联和降级记录。
- Shadow 模式状态镜像与差异记录。
"""
from __future__ import annotations

import atexit
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.services.agent_runtime.types import RuntimeTraceContext

logger = logging.getLogger(__name__)


class RuntimeVersion(StrEnum):
    """会话创建后固定使用的 Runtime 版本。"""

    LEGACY = "legacy_v1"
    LANGGRAPH_SHADOW = "langgraph_shadow_v1"
    LANGGRAPH_PRIMARY = "langgraph_primary_v1"


def resolve_runtime_version(value: str | None) -> RuntimeVersion:
    """解析 Runtime 版本，缺省保持旧链路。"""
    return RuntimeVersion(value or RuntimeVersion.LEGACY)


# ---------------------------------------------------------------------------
# Shadow 模式状态差异记录
# ---------------------------------------------------------------------------


@dataclass
class ShadowDiffRecord:
    """Shadow 模式状态差异记录。"""

    trace: RuntimeTraceContext
    legacy_response_keys: list[str]
    shadow_state_keys: list[str]
    key_diff: list[str]  # Shadow 有但 Legacy 没有的 key
    identical: bool


def run_shadow_projection(
    *,
    state: dict,
    call_model,
    call_qa_run,
    trace: RuntimeTraceContext | None = None,
) -> dict:
    """Shadow 只投影状态，不重复调用真实模型、QARun 或领域写操作。

    返回包含原始状态和差异元数据的字典。
    """
    shadow_state = dict(state)

    # 记录 Shadow 运行证据
    shadow_meta = {
        "_shadowRan": True,
        "_shadowTimestamp": datetime.now(UTC).isoformat(),
    }
    if trace is not None:
        shadow_meta["_traceContext"] = trace.to_dict()

    shadow_state["_shadowMeta"] = shadow_meta
    return shadow_state


def compute_shadow_diff(
    *,
    legacy_response: Any,
    shadow_state: dict,
    trace: RuntimeTraceContext,
) -> ShadowDiffRecord:
    """比较 Legacy 响应与 Shadow 投影状态的 key 差异。"""
    legacy_keys = sorted(_extract_response_keys(legacy_response))
    shadow_keys = sorted(k for k in shadow_state.keys() if not k.startswith("_"))
    key_diff = sorted(set(shadow_keys) - set(legacy_keys))
    return ShadowDiffRecord(
        trace=trace,
        legacy_response_keys=legacy_keys,
        shadow_state_keys=shadow_keys,
        key_diff=key_diff,
        identical=len(key_diff) == 0,
    )


def _extract_response_keys(response: Any) -> list[str]:
    """从响应对象提取 key 列表。"""
    if isinstance(response, dict):
        return list(response.keys())
    if hasattr(response, "model_dump"):
        dumped = response.model_dump()
        if isinstance(dumped, dict):
            return list(dumped.keys())
    if hasattr(response, "__dict__"):
        return [k for k in response.__dict__.keys() if not k.startswith("_")]
    return []


# ---------------------------------------------------------------------------
# 共享 Checkpointer
# ---------------------------------------------------------------------------

_shared_checkpointer = None
_shared_checkpointer_context = None


def _close_shared_checkpointer() -> None:
    """关闭共享 Postgres Checkpointer 持有的连接上下文。"""
    global _shared_checkpointer, _shared_checkpointer_context
    if _shared_checkpointer_context is not None:
        _shared_checkpointer_context.__exit__(None, None, None)
    _shared_checkpointer = None
    _shared_checkpointer_context = None


def _get_shared_checkpointer():
    """按 Agent Runtime 专用配置创建并复用 Checkpointer。"""
    global _shared_checkpointer, _shared_checkpointer_context
    if _shared_checkpointer is None:
        from app.services.agent_runtime.checkpoint_service import create_checkpointer
        from app.core.config import get_settings

        settings = get_settings()
        backend = settings.agent_runtime_checkpoint_backend
        database_url = settings.agent_runtime_checkpoint_database_url
        created = create_checkpointer(backend=backend, database_url=database_url)
        if backend == "postgres":
            # PostgresSaver.from_conn_string 返回上下文管理器，进程生命周期内保持连接可用。
            _shared_checkpointer_context = created
            _shared_checkpointer = created.__enter__()
        else:
            _shared_checkpointer = created
    return _shared_checkpointer


atexit.register(_close_shared_checkpointer)


# ---------------------------------------------------------------------------
# Graph 构建
# ---------------------------------------------------------------------------


def _build_graph_for_session(
    session: Any,
    credential: str,
    session_id: str,
    trace: RuntimeTraceContext,
):
    """为当前会话构建并返回 EmployeeTrainingGraph。

    依赖注入：将 DB session 和 service 函数通过闭包传给 Graph 节点。
    """
    from app.services.training_classroom_service import (
        _read_session,
        _recent_context_messages,
        apply_classroom_domain_event,
        persist_classroom_domain_response,
        read_classroom_event_by_request_id,
    )
    from app.services.training_agent_service import resolve_training_context
    from app.services.training_skill_registry_service import record_training_skill_call
    from app.services.agent_runtime.graphs.employee_training_graph import build_employee_training_graph

    def get_db_session_fn():
        return session

    def read_session_fn(db_session, session_id):
        return _read_session(db_session, session_id)

    def resolve_context_fn(db_session, cred, app_id):
        return resolve_training_context(db_session, cred, app_id)

    def recent_messages_fn(db_session, session_id):
        return _recent_context_messages(db_session, session_id)

    def read_by_request_id_fn(db_session, session_id, request_id):
        return read_classroom_event_by_request_id(db_session, session_id, request_id)

    def apply_fn(db_session, cred, session_id, request):
        return apply_classroom_domain_event(db_session, cred, session_id, request)

    def persist_fn(db_session, session_id, state_row, domain_result, end_user_id, request_id=None):
        return persist_classroom_domain_response(db_session, session_id, state_row, domain_result, end_user_id, request_id=request_id)

    state_row = _read_session(session, session_id)

    # 依赖加载
    model = None
    checkpointer = None
    classifier = None
    qa_run_tool = None
    build_agent_fn = None

    try:
        from app.services.agent_runtime.model_adapter import create_chat_model
        from app.core.config import get_settings
        model = create_chat_model(get_settings())
    except Exception as exc:
        logger.debug("Model 不可用: %s", exc)

    checkpointer = _get_shared_checkpointer()

    if model is not None:
        try:
            from app.services.agent_runtime.graphs.employee_training_intent import create_text_intent_classifier
            classifier = create_text_intent_classifier(model)
        except Exception as exc:
            logger.debug("Classifier 不可用: %s", exc)

    # QARun Tool 使用幂等缓存，绑定到本次 invocation
    idempotency_store: dict[str, dict] = {}

    try:
        from app.services.agent_runtime.qa_run_tool import create_qa_run_tool
        qa_run_tool = create_qa_run_tool(
            session=session,
            credential=credential,
            end_user_id=str(state_row["end_user_id"]),
            idempotency_store=idempotency_store,
        )
    except Exception as exc:
        logger.debug("QARunTool 不可用: %s", exc)

    try:
        from app.services.agent_runtime.rag_agent_factory import build_rag_answer_agent
        build_agent_fn = build_rag_answer_agent
    except Exception as exc:
        logger.debug("RAG Agent Factory 不可用: %s", exc)

    def record_skill_call_fn(session, **kwargs):
        """将 Trace 上下文注入审计记录。"""
        kwargs.setdefault("session_id", trace.thread_id)
        return record_training_skill_call(session, **kwargs)

    graph = build_employee_training_graph(
        checkpointer=checkpointer,
        model=model,
        qa_run_tool=qa_run_tool,
        get_db_session_fn=get_db_session_fn,
        read_session_fn=read_session_fn,
        resolve_context_fn=resolve_context_fn,
        recent_messages_fn=recent_messages_fn,
        read_by_request_id_fn=read_by_request_id_fn,
        apply_domain_event_fn=apply_fn,
        persist_domain_response_fn=persist_fn,
        build_agent_fn=build_agent_fn,
        classifier=classifier,
        record_skill_call_fn=record_skill_call_fn,
        system_prompt="你是员工培训课堂 AI 助手。",
    )
    return graph


# ---------------------------------------------------------------------------
# 公开入口
# ---------------------------------------------------------------------------


def submit_training_classroom_runtime_event(
    session: Any,
    credential: str,
    session_id: str,
    request: Any,
    runtime_version: RuntimeVersion,
) -> Any:
    """课堂事件入口，根据 runtime_version 分流到 Legacy / Shadow / Primary。"""
    # 生成本次调用的 Trace 上下文
    trace = RuntimeTraceContext(
        agent_invocation_id=str(uuid.uuid4()),
        thread_id=session_id,
        scenario_type="employee_training",
        runtime_version=runtime_version.value,
    )

    if runtime_version == RuntimeVersion.LEGACY:
        from app.services.training_classroom_service import submit_classroom_event
        return submit_classroom_event(session, credential, session_id, request)

    if runtime_version == RuntimeVersion.LANGGRAPH_SHADOW:
        from app.services.training_classroom_service import submit_classroom_event
        primary_response = submit_classroom_event(session, credential, session_id, request)
        shadow_state = run_shadow_projection(
            state={"sessionId": session_id, "eventType": request.eventType},
            call_model=None,
            call_qa_run=None,
            trace=trace,
        )
        diff = compute_shadow_diff(
            legacy_response=primary_response,
            shadow_state=shadow_state,
            trace=trace,
        )
        logger.debug(
            "Shadow diff for session %s: identical=%s, key_diff=%s",
            session_id, diff.identical, diff.key_diff,
        )
        return primary_response

    # LANGGRAPH_PRIMARY — 走 Graph 编排
    request_id = getattr(request, "requestId", None)
    graph_started = False
    try:
        graph = _build_graph_for_session(session, credential, session_id, trace)
        initial_state = {
            "sessionId": session_id,
            "requestId": request_id or "",
            "eventType": request.eventType,
            "payload": request.payload or {},
            "query": request.query or "",
            "_credential": credential,
            "_traceContext": trace.to_dict(),
        }
        config = {"configurable": {"thread_id": session_id}}
        graph_started = True
        result_state = graph.invoke(initial_state, config=config)

        # 更新 Trace 上下文（Graph 执行后可能填充了 qaRunId 等）
        trace.qa_run_id = result_state.get("qaRunId", "")
        trace.skill_call_id = result_state.get("skillCallId", "")

        # 从 Graph 结果组装响应
        from app.schemas.training_classroom import (
            ClassroomEventResponse,
            ClassroomControlDTO,
            ClassroomUiActionDTO,
            ClassroomCitationDTO,
            ClassroomProgressUpdateDTO,
        )

        content = result_state.get("visibleContent", "处理完成。")
        citations_raw = result_state.get("citations", [])
        citations = [ClassroomCitationDTO(**c) for c in citations_raw] if citations_raw else []
        actions_raw = result_state.get("pendingActions", [])
        ui_actions = [ClassroomUiActionDTO(**a) for a in actions_raw] if actions_raw else []
        domain = result_state.get("domainResult", {})

        # 从持久化节点回传的字段
        event_id = result_state.get("_persistedEventId", "")
        progress_raw = result_state.get("_persistedProgressUpdate")
        progress = ClassroomProgressUpdateDTO(**progress_raw) if progress_raw else None

        has_answer = any(a.actionType in {"single_choice", "true_false", "subjective"} for a in ui_actions)
        requires_input = bool(ui_actions)

        return ClassroomEventResponse(
            eventId=event_id,
            sessionId=session_id,
            eventType=result_state.get("eventType", request.eventType),
            resultState=domain.get("resultState", result_state.get("currentState", "")),
            visibleContent=content,
            classroomState=domain.get("resultState", result_state.get("currentState", "")),
            uiActions=ui_actions,
            citations=citations,
            control=ClassroomControlDTO(
                canProceed=not requires_input,
                requiresInput=requires_input,
                inputType="answer" if has_answer else ("action" if requires_input else None),
            ),
            progressUpdate=progress,
            createdAt=datetime.now(UTC).isoformat(),
        )

    except Exception as exc:
        # Graph 开始执行后无法可靠判断业务写入边界，禁止 Legacy 重放。
        if graph_started:
            logger.warning("Primary Graph 执行失败，禁止降级以避免重复副作用: %s", exc)
            raise

        # 显式降级：仅 Graph 构建阶段失败时回退 Legacy。
        logger.warning("Primary Graph 执行失败，降级到 Legacy: %s", exc)
        _record_fallback(session, session_id, request_id, str(exc))
        from app.services.training_classroom_service import submit_classroom_event
        return submit_classroom_event(session, credential, session_id, request)


def _record_fallback(session: Any, session_id: str, request_id: str | None, error: str) -> None:
    """记录降级事件到训练 Skill 审计表。"""
    try:
        from app.services.training_skill_registry_service import record_training_skill_call
        record_training_skill_call(
            session,
            skill_name="runtimeFallback",
            status="fallback",
            session_id=session_id,
            input_summary=f"requestId={request_id}",
            output_summary=f"error={error[:200]}",
        )
    except Exception:
        logger.debug("降级审计记录失败，已忽略")
