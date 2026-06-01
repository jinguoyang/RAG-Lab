"""员工培训课堂意图分类与路由类型。

规则优先 → LLM 结构化分类 → 置信度门控 → 程序校验。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 领域命令
# ---------------------------------------------------------------------------

_DOMAIN_COMMANDS: set[str] = {
    "start",
    "continue",
    "start_plan",
    "start_quiz",
    "submit_answer",
    "submit_quiz",
    "retry_teach",
    "retry_quiz",
    "next_section",
    "complete",
}

# ---------------------------------------------------------------------------
# 课堂状态 → 允许动作映射
# ---------------------------------------------------------------------------

_CLASSROOM_ALLOWED_ACTIONS: dict[str, set[str]] = {
    "INIT": {"start"},
    "PLAN": {"continue", "start_plan"},
    "TEACH": {"continue", "query"},
    "CHECK_UNDERSTAND": {"continue", "start_quiz", "query"},
    "QUIZ": {"submit_answer", "submit_quiz", "query"},
    "GRADE": {"continue", "query"},
    "REVIEW": {"continue", "retry_teach", "retry_quiz", "query"},
    "SUMMARY": {"next_section", "complete", "query"},
    "NEXT_SECTION": {"continue", "query"},
    "COMPLETED": set(),
    "OFF_TOPIC": {"continue", "query"},
}

# ---------------------------------------------------------------------------
# 安全拦截 & 快捷规则
# ---------------------------------------------------------------------------

_FORBIDDEN_TERMS: tuple[str, ...] = (
    "跳过测验",
    "直接完成课程",
    "修改评分",
    "查看其他学员成绩",
)

_REPEAT_TERMS: set[str] = {
    "重复一下",
    "再讲一遍",
    "讲简单一点",
    "举个例子",
}

# ---------------------------------------------------------------------------
# Pydantic 类型
# ---------------------------------------------------------------------------

IntentType = Literal[
    "domain_command",
    "course_qa",
    "teaching_adjustment",
    "multi_tool_task",
    "classroom_meta",
    "content_feedback",
    "off_topic",
]

DecisionIntentType = Literal[
    "domain_command",
    "course_qa",
    "teaching_adjustment",
    "multi_tool_task",
    "classroom_meta",
    "content_feedback",
    "off_topic",
    "clarification_required",
    "forbidden",
]


class DomainCommand(BaseModel):
    """从自然语言中提取的领域命令。"""

    eventType: str
    payload: dict[str, Any] = Field(default_factory=dict)


class TextIntentResult(BaseModel):
    """LLM 结构化分类输出（7 种意图）。"""

    intent: IntentType
    command: DomainCommand | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str


class TextRouteDecision(BaseModel):
    """最终路由决策（含规则追加的 clarification_required / forbidden）。"""

    intent: DecisionIntentType
    command: DomainCommand | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str


class IntentRouteContext(BaseModel):
    """意图分类所需的上下文信息。"""

    currentState: str
    allowedActions: list[str]
    currentQuestion: dict[str, Any] | None = None
    courseSummary: str = ""
    recentMessages: list[dict[str, str]] = Field(default_factory=list)
    availableSkills: list[str] = Field(default_factory=list)


class DomainCommandValidation(BaseModel):
    """领域命令校验结果。"""

    allowed: bool
    command: DomainCommand | None = None
    reason: str


# ---------------------------------------------------------------------------
# 公开函数
# ---------------------------------------------------------------------------


def get_allowed_classroom_actions(current_state: str) -> set[str]:
    """返回指定课堂状态下的允许动作集合。"""
    return set(_CLASSROOM_ALLOWED_ACTIONS.get(current_state, set()))


def validate_domain_command(
    command: DomainCommand,
    allowed_actions: set[str],
) -> DomainCommandValidation:
    """校验领域命令是否合法：事件类型已知、在允许列表中、必要字段完整。"""
    if command.eventType not in _DOMAIN_COMMANDS:
        return DomainCommandValidation(
            allowed=False,
            command=None,
            reason=f"未知的事件类型: {command.eventType}",
        )
    if command.eventType not in allowed_actions:
        return DomainCommandValidation(
            allowed=False,
            command=None,
            reason=f"当前状态下不允许执行: {command.eventType}",
        )
    if command.eventType in {"submit_answer", "submit_quiz"}:
        if not command.payload.get("questionId") or not command.payload.get("answer"):
            return DomainCommandValidation(
                allowed=False,
                command=None,
                reason="submit_answer/submit_quiz 缺少 questionId 或 answer",
            )
    return DomainCommandValidation(allowed=True, command=command, reason="ok")


def create_text_intent_classifier(model: Any) -> Any:
    """创建 LLM 结构化意图分类器（单次调用）。"""
    return model.with_structured_output(TextIntentResult)


def resolve_text_intent(
    *,
    query: str,
    ctx: IntentRouteContext,
    classifier: Any,
) -> TextRouteDecision:
    """规则优先 → LLM 分类 → 置信度门控。

    1. 安全拦截：禁止词 → forbidden
    2. 快捷规则：重复/继续等 → 直接映射
    3. LLM 结构化分类
    4. 置信度门控
    """
    # 1. 安全拦截
    for term in _FORBIDDEN_TERMS:
        if term in query:
            return TextRouteDecision(
                intent="forbidden",
                confidence=1.0,
                reason=f"命中禁止词: {term}",
            )

    # 2. 快捷规则
    rule_decision = _resolve_rule_decision(query, ctx)
    if rule_decision is not None:
        return rule_decision

    # 3. LLM 结构化分类
    try:
        result: TextIntentResult = classifier.invoke(
            {"query": query, "currentState": ctx.currentState}
        )
    except Exception:
        return TextRouteDecision(
            intent="clarification_required",
            confidence=0.0,
            reason="分类模型调用失败，请使用页面按钮或补充说明",
        )

    # 4. 置信度门控
    if result.confidence < 0.60:
        return TextRouteDecision(
            intent="clarification_required",
            command=result.command,
            confidence=result.confidence,
            reason=f"置信度过低 ({result.confidence:.2f}): {result.reason}",
        )

    # domain_command 需要更高置信度
    if result.intent == "domain_command":
        if result.confidence < 0.85:
            return TextRouteDecision(
                intent="clarification_required",
                command=result.command,
                confidence=result.confidence,
                reason=f"领域命令置信度不足 ({result.confidence:.2f}): {result.reason}",
            )
        if result.command and result.command.eventType not in set(ctx.allowedActions):
            return TextRouteDecision(
                intent="clarification_required",
                command=result.command,
                confidence=result.confidence,
                reason=f"当前状态下不允许: {result.command.eventType}",
            )

    return TextRouteDecision(
        intent=result.intent,
        command=result.command,
        confidence=result.confidence,
        reason=result.reason,
    )


# ---------------------------------------------------------------------------
# 内部规则引擎
# ---------------------------------------------------------------------------


def _resolve_rule_decision(
    query: str,
    ctx: IntentRouteContext,
) -> TextRouteDecision | None:
    """快捷规则：对语义稳定的短语做确定性路由。"""
    # 重复/教学调整
    for term in _REPEAT_TERMS:
        if term in query:
            return TextRouteDecision(
                intent="teaching_adjustment",
                confidence=1.0,
                reason=f"命中快捷规则: {term}",
            )

    # "继续" 类意图 —— 单一安全动作时直接转换
    continue_keywords = {"继续", "下一步", "下一页", "进入下一步", "开始"}
    if query.strip() in continue_keywords:
        safe_actions = {"continue", "start", "start_plan", "start_quiz", "next_section"}
        available = safe_actions & set(ctx.allowedActions)
        if len(available) == 1:
            action = next(iter(available))
            return TextRouteDecision(
                intent="domain_command",
                command=DomainCommand(eventType=action),
                confidence=1.0,
                reason=f"单一安全动作直接转换: {action}",
            )
        if len(available) > 1:
            return TextRouteDecision(
                intent="clarification_required",
                confidence=0.5,
                reason=f"多个可用动作，请明确: {sorted(available)}",
            )

    return None
