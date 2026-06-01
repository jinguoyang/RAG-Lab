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
