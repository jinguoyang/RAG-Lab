"""VisionTextProvider：图片视觉文本抽取 Provider 抽象与工厂。"""

import base64
import json
import re

from pydantic import BaseModel

from app.core.config import Settings
from app.services.qa_providers import ProviderError


class VisionTextResult(BaseModel):
    """视觉文本抽取结果 DTO。"""

    caption: str
    ocr_text: str
    structured_summary: str


class VisionTextProvider:
    """视觉文本抽取 Provider 抽象基类。"""

    def extract_text(self, image_bytes: bytes) -> VisionTextResult:
        raise NotImplementedError


class LocalVisionTextProvider(VisionTextProvider):
    """本地测试用 VisionTextProvider，返回固定数据。"""

    def extract_text(self, image_bytes: bytes) -> VisionTextResult:
        return VisionTextResult(
            caption="本地 Vision Provider 测试 caption",
            ocr_text="本地 Vision Provider 测试 OCR 文本",
            structured_summary="本地 Vision Provider 测试结构化摘要",
        )


class HttpVisionTextProvider(VisionTextProvider):
    """HTTP VisionTextProvider，调用 OpenAI-compatible vision API。"""

    def __init__(self, settings: Settings) -> None:
        endpoint = settings.vision_text_endpoint or settings.llm_endpoint
        if not endpoint:
            raise ProviderError("Vision text endpoint is required.")
        self._endpoint = endpoint
        self._api_key = settings.vision_text_api_key or settings.llm_api_key
        self._model = settings.vision_text_model or settings.llm_model
        self._max_image_side = settings.vision_text_max_image_side

    def extract_text(self, image_bytes: bytes) -> VisionTextResult:
        """调用 OpenAI-compatible vision API 抽取图片文本。"""
        import httpx

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "请分析这张图片，返回 JSON 格式：\n"
                            '{"caption": "图片简要描述", "ocr_text": "图片中所有文字", "structured_summary": "图片结构化摘要"}\n'
                            "只返回 JSON，不要 markdown 包裹。"
                        ),
                    },
                ],
            }
        ]

        try:
            response = httpx.post(
                self._endpoint,
                headers=headers,
                json={"model": self._model, "messages": messages, "temperature": 0.1},
                timeout=60,
            )
            if response.status_code >= 400:
                try:
                    error_body = response.json()
                    error_detail = error_body.get("error", {}).get("message", response.text)
                except Exception:
                    error_detail = response.text
                raise ProviderError(f"Vision API request failed: HTTP {response.status_code} - {error_detail}")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Vision API request failed: {exc}") from exc

        payload = response.json()
        try:
            content = str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Vision API response is invalid.") from exc

        data = _parse_vision_json(content)
        return VisionTextResult(
            caption=str(data.get("caption") or ""),
            ocr_text=str(data.get("ocr_text") or ""),
            structured_summary=str(data.get("structured_summary") or ""),
        )


def get_vision_text_provider(settings: Settings | None = None) -> VisionTextProvider:
    """根据配置创建 VisionTextProvider 实例。"""
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()
    provider_type = settings.vision_text_provider
    if provider_type == "local":
        return LocalVisionTextProvider()
    return HttpVisionTextProvider(settings)


def _parse_vision_json(content: str) -> dict:
    """解析 Vision API JSON 输出，兼容少量 fenced code 包裹。"""
    cleaned = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Vision API response is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ProviderError("Vision API response must be a JSON object.")
    return data
