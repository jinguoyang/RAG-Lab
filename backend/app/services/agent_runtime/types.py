"""Agent Runtime 共享类型定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeTraceContext:
    """贯穿 Graph → Tool → QARun 的 Trace 关联上下文。

    一次 Runtime 调用至少可关联以下标识（spec 10.1）：
    - agentInvocationId: 本次 Runtime 调用唯一 ID
    - threadId: LangGraph thread_id
    - scenarioType: 场景类型
    - runtimeVersion: Runtime 版本
    """

    agent_invocation_id: str
    thread_id: str
    scenario_type: str = ""
    runtime_version: str = ""
    checkpoint_id: str = ""
    # 运行时动态填充
    qa_run_id: str = ""
    skill_call_id: str = ""
    model_call_id: str = ""
    summary_version: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转为扁平字典，便于写入审计或日志。"""
        return {
            "agentInvocationId": self.agent_invocation_id,
            "threadId": self.thread_id,
            "scenarioType": self.scenario_type,
            "runtimeVersion": self.runtime_version,
            "checkpointId": self.checkpoint_id,
            "qaRunId": self.qa_run_id,
            "skillCallId": self.skill_call_id,
            "modelCallId": self.model_call_id,
            "summaryVersion": self.summary_version,
        }
