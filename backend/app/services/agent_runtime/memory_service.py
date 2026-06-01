"""Agent 上下文摘要中间件工厂。"""
from langchain.agents.middleware import SummarizationMiddleware


def create_summary_middleware(*, model, trigger_tokens: int, keep_messages: int):
    """创建 LangChain 官方摘要中间件，不新增平行手写压缩实现。"""
    return SummarizationMiddleware(
        model=model,
        trigger=("tokens", trigger_tokens),
        keep=("messages", keep_messages),
    )
