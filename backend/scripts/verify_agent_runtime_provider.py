"""探测真实 LLM Provider 对 LangChain Agent Runtime 四项能力的支持情况。

输出 JSON 报告，不输出 API Key。
失败项写 false 和错误摘要。

用法:
    python backend/scripts/verify_agent_runtime_provider.py
    python backend/scripts/verify_agent_runtime_provider.py --dry-run   # 仅验证导入，不调用 Provider
"""
from __future__ import annotations

from pathlib import Path
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
import sys
import traceback

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _probe_chat(model) -> bool:
    """发送最小消息，验证基础 chat 能力。"""
    from langchain_core.messages import HumanMessage

    resp = model.invoke([HumanMessage(content="ping")])
    return bool(resp.content)


def _probe_tool_calling(model) -> bool:
    """绑定一个真实 Tool 后调用，校验 tool_calls 中的名称和参数。"""
    from langchain_core.messages import HumanMessage
    from langchain_core.tools import tool

    @tool
    def probe_tool(query: str) -> str:
        """A probe tool for capability testing."""
        return f"echo: {query}"

    try:
        bound = model.bind_tools([probe_tool])
        resp = bound.invoke([HumanMessage(content="请调用 probe_tool，参数 query='test'")])
        if not hasattr(resp, "tool_calls") or not resp.tool_calls:
            return False
        # 校验第一个 tool_call 的名称和参数
        call = resp.tool_calls[0]
        if call.get("name") != "probe_tool":
            return False
        args = call.get("args", {})
        if args.get("query") != "test":
            return False
        return True
    except Exception:
        return False


def _probe_structured_output(model) -> bool:
    """使用 with_structured_output 验证结构化输出，不使用默认值。"""
    from langchain_core.messages import HumanMessage
    from pydantic import BaseModel

    class ProbeSchema(BaseModel):
        status: str
        count: int

    try:
        structured = model.with_structured_output(ProbeSchema)
        resp = structured.invoke([HumanMessage(content='返回 JSON: {"status": "ok", "count": 42}')])
        if not isinstance(resp, ProbeSchema):
            return False
        return resp.status == "ok" and resp.count == 42
    except Exception:
        return False


def _probe_summarization(model) -> bool:
    """发送较长文本，验证模型能返回非空摘要。"""
    from langchain_core.messages import HumanMessage

    long_text = "请用一句话总结以下内容：" + "这是一段测试文本。" * 200
    try:
        resp = model.invoke([HumanMessage(content=long_text)])
        return bool(resp.content)
    except Exception:
        return False


def run_probes(model) -> dict[str, bool | str]:
    """执行四项能力探测，返回结果字典。"""
    results: dict[str, bool | str] = {}

    for name, probe_fn in [
        ("chat", _probe_chat),
        ("toolCalling", _probe_tool_calling),
        ("structuredOutput", _probe_structured_output),
        ("summarization", _probe_summarization),
    ]:
        try:
            results[name] = probe_fn(model)
        except Exception as exc:
            results[name] = False
            results[f"{name}_error"] = "".join(traceback.format_exception_only(type(exc), exc)).strip()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="探测 LLM Provider 对 Agent Runtime 四项能力的支持")
    parser.add_argument("--dry-run", action="store_true", help="仅验证导入和配置，不调用 Provider")
    args = parser.parse_args()

    # 部分可选依赖会在导入阶段向 stdout 打印诊断。转发到 stderr，
    # 避免污染供自动化消费的 JSON stdout。
    diagnostics = StringIO()
    with redirect_stdout(diagnostics):
        from app.core.config import get_settings  # noqa: E402
        from app.services.agent_runtime.model_adapter import ProviderCapabilityReport, create_chat_model  # noqa: E402
        settings = get_settings()
    if diagnostics.getvalue():
        print(diagnostics.getvalue(), file=sys.stderr, end="")

    if args.dry_run:
        print(json.dumps({
            "dryRun": True,
            "model": settings.llm_model,
            "endpoint": bool(settings.llm_endpoint),
            "apiKey": bool(settings.llm_api_key),
        }, indent=2))
        sys.exit(0)

    diagnostics = StringIO()
    with redirect_stdout(diagnostics):
        model = create_chat_model(settings)
    if diagnostics.getvalue():
        print(diagnostics.getvalue(), file=sys.stderr, end="")
    results = run_probes(model)

    report = ProviderCapabilityReport(**{k: v for k, v in results.items() if not k.endswith("_error")})
    output = report.model_dump()
    for k, v in results.items():
        if k.endswith("_error"):
            output[k] = v

    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    print()

    if not all(v for k, v in results.items() if not k.endswith("_error")):
        sys.exit(1)


if __name__ == "__main__":
    main()
