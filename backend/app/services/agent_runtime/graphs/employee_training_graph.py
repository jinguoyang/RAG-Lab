"""EmployeeTrainingGraph — 员工培训课堂 LangGraph 编排。

18 个节点 + 条件路由，覆盖页面事件、自由文本、恢复、异常路径。
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, TypedDict

from app.schemas.training_classroom import (
    ClassroomCitationDTO,
    ClassroomDomainResult,
    ClassroomUiActionDTO,
)
from app.services.agent_runtime.graphs.employee_training_intent import (
    DomainCommand,
    IntentRouteContext,
    TextRouteDecision,
    get_allowed_classroom_actions,
    resolve_text_intent,
    validate_domain_command,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class EmployeeTrainingState(TypedDict, total=False):
    """Graph 运行时状态。"""

    sessionId: str
    requestId: str
    eventType: str
    payload: dict[str, Any]
    query: str
    currentState: str
    allowedActions: list[str]
    textDecision: dict[str, Any]
    domainResult: dict[str, Any]
    responseMode: str
    visibleContent: str
    citations: list[dict[str, Any]]
    pendingActions: list[dict[str, Any]]
    # 内部
    _inputCarrier: str
    _domainCommand: dict[str, Any]
    _validationResult: dict[str, Any]
    _idempotencyHit: bool
    _previousSnapshot: dict[str, Any] | None
    _contextRow: Any
    _kbId: Any
    _credential: str
    _endUserId: str
    _app_id: str
    _persistedEventId: str
    _persistedProgressUpdate: dict[str, Any] | None


# ---------------------------------------------------------------------------
# 节点函数（纯计算，通过闭包注入依赖）
# ---------------------------------------------------------------------------


def _make_load_context(get_session_fn, read_session_fn, resolve_context_fn, recent_messages_fn):
    """创建 load_context 节点。"""

    def load_context(state: EmployeeTrainingState) -> dict[str, Any]:
        session_id = state["sessionId"]
        db_session = get_session_fn()
        state_row = read_session_fn(db_session, session_id)
        credential = state.get("_credential", "")
        context = resolve_context_fn(db_session, credential, str(state_row["app_id"]))
        allowed = list(get_allowed_classroom_actions(state_row["current_state"]))
        return {
            "currentState": state_row["current_state"],
            "allowedActions": allowed,
            "_contextRow": state_row,
            "_kbId": context.kb_row["kb_id"] if hasattr(context, "kb_row") else None,
            "_app_id": str(state_row["app_id"]),
            "_endUserId": state_row["end_user_id"],
        }

    return load_context


def _make_get_allowed_actions():
    def get_allowed_actions(state: EmployeeTrainingState) -> dict[str, Any]:
        return {"allowedActions": list(get_allowed_classroom_actions(state.get("currentState", "")))}
    return get_allowed_actions


def _make_route_input():
    def route_input(state: EmployeeTrainingState) -> dict[str, Any]:
        event_type = state.get("eventType", "")
        query = state.get("query", "")
        if event_type and event_type not in {"query", ""}:
            return {"_inputCarrier": "page_event"}
        if query:
            return {"_inputCarrier": "free_text"}
        return {"_inputCarrier": "resume"}
    return route_input


def _make_normalize_domain_event():
    def normalize_domain_event(state: EmployeeTrainingState) -> dict[str, Any]:
        return {
            "_domainCommand": {
                "eventType": state.get("eventType", ""),
                "payload": state.get("payload", {}),
            }
        }
    return normalize_domain_event


def _make_classify_intent(classifier, record_skill_call_fn=None, get_db_session_fn=None):
    """创建 classify_text_intent 节点，并记录结构化分类审计。"""

    def classify_intent(state: EmployeeTrainingState) -> dict[str, Any]:
        ctx = IntentRouteContext(
            currentState=state.get("currentState", ""),
            allowedActions=state.get("allowedActions", []),
        )
        decision = resolve_text_intent(
            query=state.get("query", ""),
            ctx=ctx,
            classifier=classifier,
        )
        if record_skill_call_fn is not None and get_db_session_fn is not None:
            try:
                record_skill_call_fn(
                    get_db_session_fn(),
                    skill_name="classifyIntent",
                    status="success",
                    session_id=state.get("sessionId"),
                    app_id=state.get("_app_id"),
                    input_summary=f"query={state.get('query', '')[:200]}",
                    output_summary=f"intent={decision.intent};confidence={decision.confidence:.2f}",
                )
            except Exception as exc:
                logger.debug("分类审计记录失败，已忽略: %s", exc)
        return {
            "textDecision": decision.model_dump(),
            "eventType": decision.command.eventType if decision.command else state.get("eventType", ""),
            "payload": decision.command.payload if decision.command else state.get("payload", {}),
            "_domainCommand": decision.command.model_dump() if decision.command else None,
        }

    return classify_intent


def _make_parse_domain_command():
    def parse_domain_command(state: EmployeeTrainingState) -> dict[str, Any]:
        decision = state.get("textDecision", {})
        command = decision.get("command")
        if command:
            return {"_domainCommand": command}
        return {}

    return parse_domain_command


def _make_validate_domain_command():
    def validate_cmd(state: EmployeeTrainingState) -> dict[str, Any]:
        from app.services.agent_runtime.graphs.employee_training_intent import DomainCommand as DC

        raw = state.get("_domainCommand", {})
        if not raw:
            return {"_validationResult": {"allowed": False, "reason": "无领域命令"}}
        cmd = DC(eventType=raw.get("eventType", ""), payload=raw.get("payload", {}))
        allowed = set(state.get("allowedActions", []))
        result = validate_domain_command(cmd, allowed)
        return {"_validationResult": result.model_dump()}

    return validate_cmd


def _make_check_idempotency(read_by_request_id_fn, get_db_session_fn):
    """创建 check_idempotency 节点。"""

    def check_idempotency(state: EmployeeTrainingState) -> dict[str, Any]:
        request_id = state.get("requestId")
        if not request_id:
            return {"_idempotencyHit": False}
        db_session = get_db_session_fn()
        existing = read_by_request_id_fn(db_session, state["sessionId"], request_id)
        if existing is not None:
            payload = existing.get("payload", {}) if hasattr(existing, "keys") else {}
            runtime = payload.get("_runtime", {}) if isinstance(payload, dict) else {}
            snapshot = runtime.get("responseSnapshot", {})
            return {
                "_idempotencyHit": True,
                "_previousSnapshot": snapshot,
                "_persistedEventId": str(existing["event_id"]) if "event_id" in existing else "",
            }
        return {"_idempotencyHit": False}

    return check_idempotency


def _make_run_domain_event(apply_fn, get_db_session_fn):
    """创建 run_domain_event 节点，调用 apply_classroom_domain_event。"""

    def run_domain_event(state: EmployeeTrainingState) -> dict[str, Any]:
        from types import SimpleNamespace

        cmd = state.get("_domainCommand", {})
        ns = SimpleNamespace(
            eventType=cmd.get("eventType", ""),
            payload=cmd.get("payload", {}),
            query=state.get("query"),
        )
        db_session = get_db_session_fn()
        result = apply_fn(db_session, state.get("_credential", ""), state["sessionId"], ns)
        return {"domainResult": result.model_dump()}

    return run_domain_event


def _make_persist_business_state(persist_fn, get_db_session_fn):
    """创建 persist_business_state 节点 — 持久化并捕获 eventId / progressUpdate。"""

    def persist_business_state(state: EmployeeTrainingState) -> dict[str, Any]:
        domain = state.get("domainResult", {})
        if not domain:
            return {}
        db_session = get_db_session_fn()
        from app.schemas.training_classroom import ClassroomDomainResult as CDR

        domain_result = CDR(**domain)
        state_row = state.get("_contextRow")
        request_id = state.get("requestId") or None
        response = persist_fn(
            db_session, state["sessionId"], state_row, domain_result,
            state.get("_endUserId", ""), request_id=request_id,
        )
        result: dict[str, Any] = {}
        if response is not None:
            if hasattr(response, "eventId"):
                result["_persistedEventId"] = response.eventId
            if hasattr(response, "progressUpdate") and response.progressUpdate:
                result["_persistedProgressUpdate"] = response.progressUpdate.model_dump()
        return result

    return persist_business_state


def _make_persist_text_response(persist_fn, get_db_session_fn):
    """创建文本响应持久化节点，确保问答和引导也写入业务消息与事件表。"""

    def persist_text_response(state: EmployeeTrainingState) -> dict[str, Any]:
        db_session = get_db_session_fn()
        decision = state.get("textDecision", {})
        domain_result = ClassroomDomainResult(
            eventType=state.get("eventType") or decision.get("intent") or "query",
            resultState=state.get("currentState", ""),
            responseMode=state.get("responseMode", "template"),
            visibleContent=state.get("visibleContent", "处理完成。"),
            uiActions=state.get("pendingActions", []),
            citations=state.get("citations", []),
            userMessage=state.get("query") or None,
            auditType=decision.get("intent") or None,
        )
        response = persist_fn(
            db_session,
            state["sessionId"],
            state.get("_contextRow"),
            domain_result,
            state.get("_endUserId", ""),
            request_id=state.get("requestId") or None,
        )
        result: dict[str, Any] = {"domainResult": domain_result.model_dump()}
        if response is not None:
            if hasattr(response, "eventId"):
                result["_persistedEventId"] = response.eventId
            if hasattr(response, "progressUpdate") and response.progressUpdate:
                result["_persistedProgressUpdate"] = response.progressUpdate.model_dump()
        return result

    return persist_text_response


def _make_generate_content(model, qa_run_tool, build_agent_fn, checkpointer, system_prompt, trigger_tokens, keep_messages):
    """创建 generate_content 节点 — 根据 responseMode 生成补充内容。

    - teaching_narration: 模型讲解当前章节
    - rag_explain: RAG 解释错题
    - agent_task: 占位
    """
    def generate_content(state: EmployeeTrainingState) -> dict[str, Any]:
        domain = state.get("domainResult", {})
        mode = domain.get("responseMode", state.get("responseMode", "template"))
        base_content = domain.get("visibleContent", state.get("visibleContent", ""))

        def generated_result(content: str) -> dict[str, Any]:
            """同步回写领域结果，保证最终持久化内容与 API 返回一致。"""
            return {
                "visibleContent": content,
                "domainResult": {**domain, "visibleContent": content},
            }

        if mode == "teaching_narration":
            if model is not None:
                try:
                    prompt = f"请对以下教学内容做简洁的讲解引导（不超过200字）：\n{base_content[:500]}"
                    resp = model.invoke([{"role": "user", "content": prompt}])
                    narration = resp.content if hasattr(resp, "content") else str(resp)
                    return generated_result(f"{narration}\n\n---\n\n{base_content}")
                except Exception as exc:
                    logger.warning("教学讲解生成失败: %s", exc)
            return generated_result(base_content)

        if mode == "rag_explain":
            if model is not None and qa_run_tool is not None and build_agent_fn is not None:
                try:
                    agent = build_agent_fn(
                        model=model, qa_run_tool=qa_run_tool,
                        checkpointer=checkpointer,
                        trigger_tokens=trigger_tokens, keep_messages=keep_messages,
                        system_prompt=system_prompt,
                    )
                    result = agent.invoke(
                        {"messages": [{"role": "user", "content": f"请解释以下错题和知识点：\n{base_content[:500]}"}]},
                        config={"configurable": {"thread_id": state["sessionId"]}},
                    )
                    last_msg = result["messages"][-1] if result.get("messages") else None
                    if last_msg:
                        return generated_result(f"{last_msg.content}\n\n---\n\n{base_content}")
                except Exception as exc:
                    logger.warning("RAG 解释生成失败: %s", exc)
            return generated_result(base_content)

        # agent_task 占位
        return generated_result(base_content)

    return generate_content


def _make_answer_course_question(qa_run_tool, build_agent_fn, checkpointer, model, system_prompt, trigger_tokens, keep_messages):
    """创建 answer_course_question 节点，调用 RAG Agent。"""

    def answer_course_question(state: EmployeeTrainingState) -> dict[str, Any]:
        try:
            agent = build_agent_fn(
                model=model,
                qa_run_tool=qa_run_tool,
                checkpointer=checkpointer,
                trigger_tokens=trigger_tokens,
                keep_messages=keep_messages,
                system_prompt=system_prompt,
            )
            result = agent.invoke(
                {"messages": [{"role": "user", "content": state.get("query", "")}]},
                config={"configurable": {"thread_id": state["sessionId"]}},
            )
            last_msg = result["messages"][-1] if result.get("messages") else None
            content = last_msg.content if last_msg else "无法生成回答。"
            return {
                "visibleContent": content,
                "responseMode": "rag_explain",
            }
        except Exception as exc:
            logger.warning("RAG Agent 调用失败: %s", exc)
            return {
                "visibleContent": "课程材料中未找到可靠依据，请尝试换个方式提问。",
                "responseMode": "rag_explain",
            }

    return answer_course_question


def _make_regenerate_teaching_response():
    """创建 regenerate_teaching_response 节点（教学风格调整）。"""

    def regenerate_teaching_response(state: EmployeeTrainingState) -> dict[str, Any]:
        return {
            "visibleContent": "好的，让我换一种方式来讲解这个知识点。",
            "responseMode": "teaching_narration",
        }

    return regenerate_teaching_response


def _make_run_skill_agent():
    """创建 run_skill_agent 节点（多工具任务，占位）。"""

    def run_skill_agent(state: EmployeeTrainingState) -> dict[str, Any]:
        return {
            "visibleContent": "多工具任务执行中，当前为占位实现。",
            "responseMode": "agent_task",
        }

    return run_skill_agent


def _make_query_classroom_status():
    """创建 query_classroom_status 节点（只读查询）。"""

    def query_classroom_status(state: EmployeeTrainingState) -> dict[str, Any]:
        current = state.get("currentState", "UNKNOWN")
        return {
            "visibleContent": f"当前课堂状态：{current}",
            "responseMode": "template",
        }

    return query_classroom_status


def _make_record_content_feedback(get_db_session_fn):
    """创建 record_content_feedback 节点。"""

    def record_content_feedback(state: EmployeeTrainingState) -> dict[str, Any]:
        return {
            "visibleContent": "感谢你的反馈，我们会记录并审核。",
            "responseMode": "template",
        }

    return record_content_feedback


def _make_build_guidance_response():
    """创建 build_guidance_response 节点（off_topic / forbidden 引导）。"""

    def build_guidance_response(state: EmployeeTrainingState) -> dict[str, Any]:
        decision = state.get("textDecision", {})
        intent = decision.get("intent", "")
        if intent == "forbidden":
            return {
                "visibleContent": "该操作不允许执行。请使用页面按钮完成学习流程。",
                "responseMode": "template",
            }
        return {
            "visibleContent": "这个问题偏离了当前课程目标。请回到当前课程内容，或提出与本节材料相关的问题。",
            "responseMode": "template",
        }

    return build_guidance_response


def _make_request_clarification():
    """创建 request_clarification 节点。"""

    def request_clarification(state: EmployeeTrainingState) -> dict[str, Any]:
        allowed = state.get("allowedActions", [])
        hint = "、".join(allowed[:3]) if allowed else "页面按钮"
        return {
            "visibleContent": f"我没有完全理解你的意图。你可以使用 {hint} 来操作，或补充更多细节。",
            "responseMode": "template",
        }

    return request_clarification


def _make_compose_response():
    """创建 compose_response 节点 — 从 domainResult / _previousSnapshot / 上游节点读取最终可见内容。"""

    def compose_response(state: EmployeeTrainingState) -> dict[str, Any]:
        # 幂等命中时，从快照恢复
        if state.get("_idempotencyHit") and state.get("_previousSnapshot"):
            snap = state["_previousSnapshot"]
            return {
                "visibleContent": snap.get("visibleContent", ""),
                "citations": snap.get("citations", []),
                "pendingActions": snap.get("uiActions", []),
                "responseMode": snap.get("responseMode", "template"),
                "domainResult": {
                    "eventType": snap.get("eventType", state.get("eventType", "")),
                    "resultState": snap.get("resultState", state.get("currentState", "")),
                    "responseMode": snap.get("responseMode", "template"),
                    "visibleContent": snap.get("visibleContent", ""),
                    "uiActions": snap.get("uiActions", []),
                    "citations": snap.get("citations", []),
                    "progressUpdate": snap.get("progressUpdate"),
                },
                "_persistedProgressUpdate": snap.get("progressUpdate"),
            }

        content = state.get("visibleContent", "")
        if not content:
            domain = state.get("domainResult", {})
            if isinstance(domain, dict):
                content = domain.get("visibleContent", "")
        if not content:
            content = "处理完成。"

        # 同步 citations、uiActions、responseMode 到顶层
        domain = state.get("domainResult", {})
        result: dict[str, Any] = {"visibleContent": content}
        if isinstance(domain, dict):
            if domain.get("citations") and not state.get("citations"):
                result["citations"] = domain["citations"]
            if domain.get("uiActions") and not state.get("pendingActions"):
                result["pendingActions"] = domain["uiActions"]
            if domain.get("responseMode") and not state.get("responseMode"):
                result["responseMode"] = domain["responseMode"]
        return result

    return compose_response


def _make_persist_and_checkpoint():
    """创建 persist_and_checkpoint 节点。

    Checkpoint 由 LangGraph compile(checkpointer=...) 自动管理，
    此节点仅作为图终止前的直通占位。
    """

    def persist_and_checkpoint(state: EmployeeTrainingState) -> dict[str, Any]:
        return {}

    return persist_and_checkpoint


# ---------------------------------------------------------------------------
# 条件路由函数
# ---------------------------------------------------------------------------


def route_after_load(state: EmployeeTrainingState) -> str:
    """load_context 后路由到 route_input。"""
    return "route_input"


def route_input_decision(state: EmployeeTrainingState) -> str:
    """根据输入载体路由。"""
    carrier = state.get("_inputCarrier", "")
    if carrier == "page_event":
        return "normalize_domain_event"
    if carrier == "free_text":
        return "check_text_idempotency"
    return "compose_response"


def route_after_classify(state: EmployeeTrainingState) -> str:
    """分类后按意图路由。"""
    decision = state.get("textDecision", {})
    intent = decision.get("intent", "")
    if intent == "domain_command":
        return "parse_domain_command"
    if intent == "course_qa":
        return "answer_course_question"
    if intent == "teaching_adjustment":
        return "regenerate_teaching_response"
    if intent == "multi_tool_task":
        return "run_skill_agent"
    if intent == "classroom_meta":
        return "query_classroom_status"
    if intent == "content_feedback":
        return "record_content_feedback"
    if intent in ("off_topic", "forbidden"):
        return "build_guidance_response"
    if intent == "clarification_required":
        return "request_clarification"
    return "request_clarification"


def route_after_validation(state: EmployeeTrainingState) -> str:
    """校验通过 → 幂等检查；校验失败 → 澄清。"""
    result = state.get("_validationResult", {})
    if result.get("allowed", False):
        return "check_idempotency"
    return "request_clarification"


def route_after_idempotency(state: EmployeeTrainingState) -> str:
    """幂等命中 → 直接组装响应；未命中 → 执行领域事件。"""
    if state.get("_idempotencyHit", False):
        return "compose_response"
    return "run_domain_event"


def route_after_text_idempotency(state: EmployeeTrainingState) -> str:
    """文本幂等命中直接回放；未命中再执行分类和 Agent。"""
    if state.get("_idempotencyHit", False):
        return "compose_response"
    return "classify_text_intent"


def route_after_domain_event(state: EmployeeTrainingState) -> str:
    """领域事件执行后按 responseMode 决定是否先生成最终正文。"""
    domain = state.get("domainResult", {})
    if domain.get("responseMode") in {"teaching_narration", "rag_explain", "agent_task"}:
        return "generate_content"
    return "persist_business_state"


def route_after_persist(state: EmployeeTrainingState) -> str:
    """业务响应已持久化，进入统一响应组装。"""
    return "compose_response"


def route_after_compose(state: EmployeeTrainingState) -> str:
    """组装后 → 持久化 + checkpoint。"""
    return "persist_and_checkpoint"


# ---------------------------------------------------------------------------
# Graph 构建器
# ---------------------------------------------------------------------------


def build_employee_training_graph(
    *,
    checkpointer=None,
    model=None,
    qa_run_tool=None,
    get_db_session_fn=None,
    read_session_fn=None,
    resolve_context_fn=None,
    recent_messages_fn=None,
    read_by_request_id_fn=None,
    apply_domain_event_fn=None,
    persist_domain_response_fn=None,
    build_agent_fn=None,
    classifier=None,
    record_skill_call_fn=None,
    system_prompt: str = "",
    trigger_tokens: int = 2000,
    keep_messages: int = 6,
):
    """构建 EmployeeTrainingGraph StateGraph 并编译返回。

    所有外部依赖通过参数注入，便于测试时 mock。
    """
    from langgraph.graph import END, StateGraph

    # 创建节点
    load_context = _make_load_context(get_db_session_fn, read_session_fn, resolve_context_fn, recent_messages_fn)
    get_allowed_actions = _make_get_allowed_actions()
    route_input = _make_route_input()
    normalize_domain_event = _make_normalize_domain_event()
    classify_intent = _make_classify_intent(classifier, record_skill_call_fn, get_db_session_fn)
    parse_domain_command = _make_parse_domain_command()
    validate_cmd = _make_validate_domain_command()
    check_idempotency = _make_check_idempotency(read_by_request_id_fn, get_db_session_fn)
    check_text_idempotency = _make_check_idempotency(read_by_request_id_fn, get_db_session_fn)
    run_domain_event = _make_run_domain_event(apply_domain_event_fn, get_db_session_fn)
    persist_business_state = _make_persist_business_state(persist_domain_response_fn, get_db_session_fn)
    persist_text_response = _make_persist_text_response(persist_domain_response_fn, get_db_session_fn)
    answer_course_q = _make_answer_course_question(qa_run_tool, build_agent_fn, checkpointer, model, system_prompt, trigger_tokens, keep_messages)
    regenerate_teaching = _make_regenerate_teaching_response()
    run_skill = _make_run_skill_agent()
    query_status = _make_query_classroom_status()
    record_feedback = _make_record_content_feedback(get_db_session_fn)
    build_guidance = _make_build_guidance_response()
    request_clarification = _make_request_clarification()
    compose_response = _make_compose_response()
    generate_content = _make_generate_content(model, qa_run_tool, build_agent_fn, checkpointer, system_prompt, trigger_tokens, keep_messages)
    persist_checkpoint = _make_persist_and_checkpoint()

    # 构建图
    graph = StateGraph(EmployeeTrainingState)

    graph.add_node("load_context", load_context)
    graph.add_node("route_input", route_input)
    graph.add_node("normalize_domain_event", normalize_domain_event)
    graph.add_node("classify_text_intent", classify_intent)
    graph.add_node("parse_domain_command", parse_domain_command)
    graph.add_node("validate_domain_command", validate_cmd)
    graph.add_node("check_idempotency", check_idempotency)
    graph.add_node("check_text_idempotency", check_text_idempotency)
    graph.add_node("run_domain_event", run_domain_event)
    graph.add_node("persist_business_state", persist_business_state)
    graph.add_node("persist_text_response", persist_text_response)
    graph.add_node("answer_course_question", answer_course_q)
    graph.add_node("regenerate_teaching_response", regenerate_teaching)
    graph.add_node("run_skill_agent", run_skill)
    graph.add_node("query_classroom_status", query_status)
    graph.add_node("record_content_feedback", record_feedback)
    graph.add_node("build_guidance_response", build_guidance)
    graph.add_node("request_clarification", request_clarification)
    graph.add_node("compose_response", compose_response)
    graph.add_node("persist_and_checkpoint", persist_checkpoint)
    graph.add_node("generate_content", generate_content)

    # 入口
    graph.set_entry_point("load_context")

    # 边
    graph.add_edge("load_context", "route_input")

    graph.add_conditional_edges("route_input", route_input_decision, {
        "normalize_domain_event": "normalize_domain_event",
        "check_text_idempotency": "check_text_idempotency",
        "compose_response": "compose_response",
    })

    graph.add_edge("normalize_domain_event", "check_idempotency")

    graph.add_conditional_edges("check_text_idempotency", route_after_text_idempotency, {
        "compose_response": "compose_response",
        "classify_text_intent": "classify_text_intent",
    })

    graph.add_conditional_edges("classify_text_intent", route_after_classify, {
        "parse_domain_command": "parse_domain_command",
        "answer_course_question": "answer_course_question",
        "regenerate_teaching_response": "regenerate_teaching_response",
        "run_skill_agent": "run_skill_agent",
        "query_classroom_status": "query_classroom_status",
        "record_content_feedback": "record_content_feedback",
        "build_guidance_response": "build_guidance_response",
        "request_clarification": "request_clarification",
    })

    graph.add_edge("parse_domain_command", "validate_domain_command")

    graph.add_conditional_edges("validate_domain_command", route_after_validation, {
        "check_idempotency": "check_idempotency",
        "request_clarification": "request_clarification",
    })

    graph.add_conditional_edges("check_idempotency", route_after_idempotency, {
        "compose_response": "compose_response",
        "run_domain_event": "run_domain_event",
    })

    graph.add_conditional_edges("run_domain_event", route_after_domain_event, {
        "generate_content": "generate_content",
        "persist_business_state": "persist_business_state",
    })

    graph.add_conditional_edges("persist_business_state", route_after_persist, {
        "generate_content": "generate_content",
        "compose_response": "compose_response",
    })

    graph.add_edge("generate_content", "persist_business_state")

    # 所有自由文本叶子节点都要先写入业务消息和事件表。
    for leaf in [
        "answer_course_question",
        "regenerate_teaching_response",
        "run_skill_agent",
        "query_classroom_status",
        "record_content_feedback",
        "build_guidance_response",
        "request_clarification",
    ]:
        graph.add_edge(leaf, "persist_text_response")

    graph.add_edge("persist_text_response", "compose_response")
    graph.add_edge("compose_response", "persist_and_checkpoint")
    graph.add_edge("persist_and_checkpoint", END)

    return graph.compile(checkpointer=checkpointer)
