"""平台 Skill 白名单适配器。"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlatformSkill:
    """平台级 Skill 描述，首版只保留当前执行需要的字段。"""

    name: str
    scenarios: set[str] = field(default_factory=set)
    readonly: bool = True


def select_allowed_skills(skills: list[PlatformSkill], *, scenario_type: str) -> list[PlatformSkill]:
    """只返回当前场景允许暴露的 Skill。"""
    return [skill for skill in skills if scenario_type in skill.scenarios]
