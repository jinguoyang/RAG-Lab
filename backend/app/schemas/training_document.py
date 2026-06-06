"""员工培训文档查询 DTO。"""
from __future__ import annotations

from pydantic import BaseModel


class TrainingDocumentDTO(BaseModel):
    """ex-app 编辑学习计划时可选择的知识库文档。"""

    documentId: str
    title: str
    category: str | None = None
    difficulty: str | None = None
    summary: str | None = None
