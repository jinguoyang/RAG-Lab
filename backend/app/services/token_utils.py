"""共享 Token 估算和融合工具函数。

避免在多个模块中重复实现相同逻辑。
"""


def estimate_tokens(text: str) -> int:
    """估算 token 数量。

    轻量级启发式：ASCII 字符按 4:1，非 ASCII（如中文）按 1:1。

    Args:
        text: 输入文本

    Returns:
        估算的 token 数
    """
    if not text:
        return 0
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return max(1, ascii_chars // 4 + non_ascii_chars)


def rrf_score(rank: int, k: int = 60) -> float:
    """计算 RRF (Reciprocal Rank Fusion) 分数。

    Args:
        rank: 排名（从 0 开始）
        k: RRF K 参数

    Returns:
        RRF 分数
    """
    return 1.0 / (k + rank)
