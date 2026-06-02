"""平台 Skill 适配器 — 将平台 Skill Registry 转换为 LangChain Tool。

职责：
- 按场景筛选允许暴露的 Skill。
- 将 PlatformSkill 转换为带 Schema 校验的 LangChain StructuredTool。
- 统一超时、预算和审计边界。
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import StrEnum
from time import perf_counter
from typing import Any, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 读写等级
# ---------------------------------------------------------------------------


class SkillSideEffectLevel(StrEnum):
    """Skill 副作用等级，用于权限和审计分级。"""

    READ_ONLY = "read_only"  # 不修改任何外部状态
    WRITE_SAFE = "write_safe"  # 写入审计/会话记录，不修改业务实体
    WRITE_DESTRUCTIVE = "write_destructive"  # 修改业务实体（需额外确认）


# ---------------------------------------------------------------------------
# Skill 描述
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlatformSkill:
    """平台级 Skill 描述，满足 spec 9.2 全部字段要求。"""

    name: str
    description: str = ""
    scenarios: set[str] = field(default_factory=set)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    side_effect_level: SkillSideEffectLevel = SkillSideEffectLevel.READ_ONLY
    allowed_agents: set[str] = field(default_factory=set)  # 空集表示不限
    timeout_seconds: float = 30.0
    max_retries: int = 0
    budget_calls_per_session: int = 0  # 0 表示不限
    audit_required: bool = True


# ---------------------------------------------------------------------------
# 筛选
# ---------------------------------------------------------------------------


def select_allowed_skills(
    skills: list[PlatformSkill],
    *,
    scenario_type: str,
    agent_id: str | None = None,
) -> list[PlatformSkill]:
    """返回当前场景（和可选 Agent）允许暴露的 Skill。"""
    result = []
    for skill in skills:
        if scenario_type not in skill.scenarios:
            continue
        if skill.allowed_agents and agent_id and agent_id not in skill.allowed_agents:
            continue
        result.append(skill)
    return result


# ---------------------------------------------------------------------------
# Pydantic Schema 构建
# ---------------------------------------------------------------------------


def _build_pydantic_input_model(name: str, json_schema: dict[str, Any]) -> type[BaseModel]:
    """从 JSON Schema 构建 Pydantic BaseModel 作为 StructuredTool 的 args_schema。"""
    properties = json_schema.get("properties", {})
    required_set = set(json_schema.get("required", []))
    fields_spec: dict[str, Any] = {}
    for field_name, field_def in properties.items():
        python_type = _json_type_to_python(field_def)
        default = ... if field_name in required_set else None
        description = field_def.get("description", "")
        fields_spec[field_name] = (python_type, Field(default, description=description))
    return create_model(f"{name}Input", **fields_spec)


def _json_type_to_python(field_def: dict[str, Any]) -> type:
    """将 JSON Schema type 映射为 Python 类型。"""
    json_type = field_def.get("type", "string")
    mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return mapping.get(json_type, Any)


# 重新导入 Field 用于动态模型构建
from pydantic import Field  # noqa: E402


# ---------------------------------------------------------------------------
# Tool 转换
# ---------------------------------------------------------------------------


def create_skill_tool(
    skill: PlatformSkill,
    *,
    invoke_fn: Callable[..., Any],
    record_call_fn: Callable[..., Any] | None = None,
    get_call_count_fn: Callable[[], int] | None = None,
) -> StructuredTool:
    """将单个 PlatformSkill 转换为带 Schema、超时和审计的 LangChain StructuredTool。

    Parameters
    ----------
    skill:
        平台 Skill 描述。
    invoke_fn:
        ``(**kwargs) -> dict`` 实际执行回调。
    record_call_fn:
        ``(skill_name, status, input_summary, output_summary, error_code, latency_ms) -> None``
        审计回调，仅在 ``skill.audit_required`` 时调用。
    get_call_count_fn:
        ``() -> int`` 返回当前会话已调用次数，用于预算检查。
    """
    input_model = _build_pydantic_input_model(skill.name, skill.input_schema)

    def _execute(**kwargs: Any) -> dict:
        # 预算检查
        if skill.budget_calls_per_session > 0 and get_call_count_fn is not None:
            current = get_call_count_fn()
            if current >= skill.budget_calls_per_session:
                raise SkillBudgetExceededError(
                    f"Skill {skill.name} 已达单会话调用上限 {skill.budget_calls_per_session}"
                )

        max_attempts = 1 + (skill.max_retries if skill.side_effect_level == SkillSideEffectLevel.READ_ONLY else 0)
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            started = perf_counter()
            try:
                result = _invoke_with_timeout(invoke_fn, kwargs, skill.timeout_seconds)
            except SkillTimeoutError:
                _maybe_record_audit(skill, record_call_fn, "timeout", kwargs, None, SkillTimeoutError("timeout"), started)
                raise
            except Exception as exc:
                last_exc = exc
                _maybe_record_audit(skill, record_call_fn, "failed", kwargs, None, exc, started)
                if attempt < max_attempts - 1:
                    continue
                raise

            latency_ms = round((perf_counter() - started) * 1000)
            _maybe_record_audit(skill, record_call_fn, "success", kwargs, result, None, started)
            return result
        raise last_exc  # type: ignore[misc]

    return StructuredTool.from_function(
        func=_execute,
        name=skill.name,
        description=skill.description,
        args_schema=input_model,
    )


def create_skill_tools(
    skills: list[PlatformSkill],
    *,
    invoke_fn_map: dict[str, Callable[..., Any]],
    record_call_fn: Callable[..., Any] | None = None,
    get_call_count_fn: Callable[[str], int] | None = None,
) -> list[StructuredTool]:
    """批量将 PlatformSkill 列表转换为 LangChain StructuredTool 列表。"""
    tools = []
    for skill in skills:
        invoke_fn = invoke_fn_map.get(skill.name)
        if invoke_fn is None:
            logger.warning("Skill %s 无对应 invoke_fn，跳过", skill.name)
            continue
        budget_fn = (lambda n=skill.name: get_call_count_fn(n)) if get_call_count_fn else None
        tools.append(
            create_skill_tool(
                skill,
                invoke_fn=invoke_fn,
                record_call_fn=record_call_fn,
                get_call_count_fn=budget_fn,
            )
        )
    return tools


# ---------------------------------------------------------------------------
# 审计辅助
# ---------------------------------------------------------------------------


def _maybe_record_audit(
    skill: PlatformSkill,
    record_call_fn: Callable[..., Any] | None,
    status: str,
    input_kwargs: dict,
    result: Any,
    exc: Exception | None,
    started: float,
) -> None:
    """在审计回调可用且 Skill 要求审计时记录调用。"""
    if not skill.audit_required or record_call_fn is None:
        return
    try:
        record_call_fn(
            skill_name=skill.name,
            status=status,
            input_summary=json.dumps(input_kwargs, ensure_ascii=False, default=str)[:500],
            output_summary=json.dumps(result, ensure_ascii=False, default=str)[:500] if result else None,
            error_code=type(exc).__name__ if exc else None,
            latency_ms=round((perf_counter() - started) * 1000),
        )
    except Exception as audit_exc:
        logger.debug("Skill %s 审计记录失败，已忽略: %s", skill.name, audit_exc)


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class SkillBudgetExceededError(Exception):
    """Skill 单会话调用次数超限。"""


class SkillTimeoutError(TimeoutError):
    """Skill 执行超过平台允许的时限。"""


def _invoke_with_timeout(invoke_fn: Callable, kwargs: dict, timeout_seconds: float) -> Any:
    """使用 ThreadPoolExecutor 对同步 Skill 设置超时。"""
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(invoke_fn, **kwargs)
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as exc:
        raise SkillTimeoutError(f"Skill 执行超时: {timeout_seconds}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
