"""平台 Agent Runtime 场景注册表。"""
from collections.abc import Callable


class ScenarioGraphRegistry:
    """按场景注册 Graph 构建函数，避免 Runtime 写死课堂语义。"""

    def __init__(self) -> None:
        self._builders: dict[str, Callable] = {}

    def register(self, scenario_type: str, builder: Callable) -> None:
        self._builders[scenario_type] = builder

    def get(self, scenario_type: str) -> Callable | None:
        return self._builders.get(scenario_type)


# 进程级单例
_scenario_registry = ScenarioGraphRegistry()


def get_scenario_registry() -> ScenarioGraphRegistry:
    """获取全局场景注册表。"""
    return _scenario_registry


def _register_builtin_scenarios() -> None:
    """注册内置场景 Graph builder。"""
    from app.services.agent_runtime.graphs.internal_customer_service_graph import (
        build_internal_customer_service_graph,
    )

    _scenario_registry.register("knowledge_qa", build_internal_customer_service_graph)


_register_builtin_scenarios()
