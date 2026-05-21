"""Task 7: 小米 API Key 真实开发复测脚本。

验证小米 endpoint 是否支持图片消息。
结果记录到 docs/06-发布与运维/2026-05-21-vision-provider-retest.md
"""

import base64
import json
import struct
import sys
import zlib
from pathlib import Path

# 添加 backend 到 Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import Settings
from app.services.qa_providers import ProviderError
from app.services.vision_text_provider import HttpVisionTextProvider


def make_tiny_png() -> bytes:
    """创建一个 1x1 白色 PNG 用于测试。"""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    raw_data = b"\x00\xff\xff\xff"
    compressed = zlib.compress(raw_data)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc
    iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    return signature + ihdr + idat + iend


def main() -> None:
    """执行小米 API 图片消息复测。"""
    print("=" * 60)
    print("Task 7: 小米 API Key 真实开发复测")
    print("=" * 60)

    # 加载配置
    settings = Settings()

    # 修正 endpoint 格式（如果需要）
    endpoint = settings.llm_endpoint
    if endpoint and not endpoint.endswith("/chat/completions"):
        endpoint = f"{endpoint.rstrip('/')}/chat/completions"
        print(f"  [INFO] 修正 endpoint 为: {endpoint}")

    # 检查配置
    print("\n[Step 1] 检查 .env 配置")
    print(f"  LLM Provider: {settings.llm_provider}")
    print(f"  LLM Endpoint: {endpoint}")
    print(f"  LLM Model: {settings.llm_model}")
    print(f"  API Key: {'*' * 8 if settings.llm_api_key else 'NOT SET'}")
    print(f"  Vision Text Provider: {settings.vision_text_provider}")

    if settings.llm_provider != "http":
        print("\n[ERROR] LLM Provider 不是 http，无法测试小米 API")
        return

    if not settings.llm_endpoint:
        print("\n[ERROR] LLM Endpoint 未配置")
        return

    if not settings.llm_api_key:
        print("\n[ERROR] LLM API Key 未配置")
        return

    # 创建测试图片
    print("\n[Step 2] 创建测试图片")
    png_bytes = make_tiny_png()
    print(f"  图片大小: {len(png_bytes)} bytes")

    # 调用 Vision API
    print("\n[Step 3] 调用小米 Vision API")
    try:
        # 创建修正后的 settings
        corrected_settings = Settings(
            _env_file=None,
            RAG_LAB_LLM_PROVIDER=settings.llm_provider,
            RAG_LAB_LLM_ENDPOINT=endpoint,
            RAG_LAB_LLM_API_KEY=settings.llm_api_key,
            RAG_LAB_LLM_MODEL=settings.llm_model,
            RAG_LAB_VISION_TEXT_PROVIDER="http",
        )
        provider = HttpVisionTextProvider(corrected_settings)
        print(f"  [DEBUG] Provider endpoint: {provider._endpoint}")
        print(f"  [DEBUG] Provider model: {provider._model}")
        print(f"  [DEBUG] Provider API key: {'*' * 8 if provider._api_key else 'NOT SET'}")
        result = provider.extract_text(png_bytes)
        print(f"  caption: {result.caption[:100]}...")
        print(f"  ocr_text: {result.ocr_text[:100]}...")
        print(f"  structured_summary: {result.structured_summary[:100]}...")
        status = "success"
        error_msg = None
    except ProviderError as exc:
        error_msg = str(exc)
        print(f"  [ProviderError] {error_msg}")

        # 判断失败类型
        if "not valid JSON" in error_msg or "must be a JSON object" in error_msg:
            status = "unsupported"
        elif "No endpoints found that support image input" in error_msg:
            status = "unsupported"
        elif "request failed" in error_msg or "timeout" in error_msg.lower():
            status = "runtime_failed"
        else:
            status = "runtime_failed"
    except Exception as exc:
        error_msg = str(exc)
        print(f"  [Exception] {error_msg}")
        status = "runtime_failed"

    # 输出结果
    print("\n[Step 4] 复测结果")
    print(f"  Status: {status}")
    print(f"  Model: {settings.llm_model}")
    print(f"  Endpoint: {settings.llm_endpoint}")
    if error_msg:
        print(f"  Error: {error_msg}")

    # 写入结果文件
    write_retest_result(settings, status, error_msg)


def write_retest_result(settings: Settings, status: str, error_msg: str | None) -> None:
    """写入复测结果到 markdown 文件。"""
    output_dir = Path(__file__).parent.parent.parent / "docs" / "06-发布与运维"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "2026-05-21-vision-provider-retest.md"

    content = f"""# Vision Provider 复测结果

**日期:** 2026-05-21
**Backlog:** B-223
**Task:** 7 - 小米 API Key 真实开发复测

## 测试环境

- **LLM Provider:** {settings.llm_provider}
- **LLM Endpoint:** {settings.llm_endpoint}
- **LLM Model:** {settings.llm_model}
- **API Key:** 已配置（不输出）
- **Vision Text Provider:** {settings.vision_text_provider}

## 测试方法

使用 1x1 白色 PNG 图片调用小米 Vision API，验证 endpoint 是否支持图片消息。

## 复测结果

**状态:** `{status}`

| 项目 | 值 |
|------|-----|
| 模型名 | {settings.llm_model} |
| Endpoint 类型 | OpenAI-compatible |
| 状态 | {status} |

"""

    if status == "success":
        content += """## 分析

小米 endpoint 支持图片消息，Vision API 调用成功。

**下一步建议:**
- 可以继续使用小米 endpoint 进行图片多模态 RAG
- 建议在生产环境中使用更大的测试图片验证 OCR 和 caption 质量
"""
    elif status == "unsupported":
        content += f"""## 分析

小米 endpoint 不支持图片消息，或返回格式不符合预期。

**错误信息:**
```
{error_msg}
```

**下一步建议:**
- 检查小米 API 文档确认是否支持图片消息
- 考虑使用其他支持图片的模型（如 qwen-vl-max）
- 或者使用专门的 Vision API 服务
"""
    elif status == "runtime_failed":
        content += f"""## 分析

小米 API 调用失败，可能是网络、凭据或限流问题。

**错误信息:**
```
{error_msg}
```

**下一步建议:**
- 检查网络连接
- 验证 API Key 是否有效
- 检查是否有速率限制
- 查看小米 API 文档确认错误码含义
"""

    output_file.write_text(content, encoding="utf-8")
    print(f"\n[Step 5] 结果已写入: {output_file}")


if __name__ == "__main__":
    main()
