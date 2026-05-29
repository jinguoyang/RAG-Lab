"""培训模块 LLM 结构化 JSON 解析服务。"""

from __future__ import annotations

import json
import re


class TrainingLLMOutputError(ValueError):
    """LLM 输出无法解析为期望的 JSON 结构。"""


def parse_training_json(text: str, required_keys: set[str] | None = None) -> dict | list:
    """解析 LLM JSON 输出，兼容 fenced code 包裹。

    Args:
        text: LLM 原始输出文本。
        required_keys: 当非空时，解析结果必须为 dict 且包含所有指定 key。

    Returns:
        解析后的 dict 或 list（仅当 required_keys 为空时允许 list）。

    Raises:
        TrainingLLMOutputError: 文本为空、JSON 无效、类型不符或缺少必需字段。
    """
    if required_keys is None:
        required_keys = set()

    cleaned = text.strip()
    if not cleaned:
        raise TrainingLLMOutputError("LLM 输出为空。")

    # 尝试从 fenced code block 中提取内容
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise TrainingLLMOutputError("LLM 输出不是有效的 JSON。") from exc

    # 当要求必需字段时，结果必须是 dict
    if required_keys and not isinstance(data, dict):
        raise TrainingLLMOutputError(
            f"LLM 输出必须是 JSON object，实际为 {type(data).__name__}。"
        )

    # 校验必需字段
    if required_keys:
        missing = required_keys - data.keys()
        if missing:
            raise TrainingLLMOutputError(
                f"LLM 输出缺少必需字段：{', '.join(sorted(missing))}。"
            )

    return data
