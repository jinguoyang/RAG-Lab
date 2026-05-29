"""培训 Skill Registry DTO。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TrainingSkillDTO(BaseModel):
    skillName: str
    description: str
    inputSchema: dict[str, Any] = Field(default_factory=dict)
    outputSchema: dict[str, Any] = Field(default_factory=dict)
