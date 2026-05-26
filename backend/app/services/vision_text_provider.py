"""VisionTextProvider：图片视觉文本抽取 Provider 抽象与工厂。"""

import base64
import json
import mimetypes
import re

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.services.qa_providers import ProviderError


class VisionTextResult(BaseModel):
    """视觉文本抽取结果 DTO。"""

    caption: str
    ocr_text: str
    structured_summary: str
    metadata: dict = Field(default_factory=dict)


class VisionTextRequest(BaseModel):
    """图片视觉文本抽取请求，不携带任何密钥或日志敏感字段。"""

    file_name: str
    mime_type: str | None
    image_bytes: bytes
    max_completion_tokens: int = 800


class VisionTextProvider:
    """视觉文本抽取 Provider 抽象基类。"""

    def extract_text(self, request: VisionTextRequest | bytes) -> VisionTextResult:
        raise NotImplementedError


class LocalVisionTextProvider(VisionTextProvider):
    """本地测试用 VisionTextProvider，返回固定数据。"""

    def extract_text(self, request: VisionTextRequest | bytes) -> VisionTextResult:
        normalized = _normalize_request(request)
        return VisionTextResult(
            caption="本地 Vision Provider 测试 caption",
            ocr_text="本地 Vision Provider 测试 OCR 文本",
            structured_summary="本地 Vision Provider 测试结构化摘要",
            metadata={
                "provider": "local",
                "model": "local-vision-text",
                "mimeType": normalized.mime_type,
                "fileSize": len(normalized.image_bytes),
            },
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
        self._auth_header = settings.vision_text_auth_header

    def extract_text(self, request: VisionTextRequest | bytes) -> VisionTextResult:
        """调用 OpenAI-compatible vision API 抽取图片文本。"""
        import httpx

        normalized = _normalize_request(request)
        b64_image = base64.b64encode(normalized.image_bytes).decode("utf-8")
        if len(b64_image.encode("utf-8")) > 50 * 1024 * 1024:
            raise ProviderError("IMAGE_TOO_LARGE: Base64 encoded image exceeds 50 MB.")

        mime_type = _resolve_mime_type(normalized.file_name, normalized.mime_type)
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            if self._auth_header.lower() == "authorization":
                headers["Authorization"] = f"Bearer {self._api_key}"
            else:
                headers["api-key"] = self._api_key

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
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
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.1,
                    "max_completion_tokens": normalized.max_completion_tokens,
                },
                timeout=60,
            )
            if response.status_code >= 400:
                try:
                    error_body = response.json()
                    error_detail = error_body.get("error", {}).get("message", response.text)
                except Exception:
                    error_detail = response.text
                raise ProviderError(f"Vision API request failed: HTTP {response.status_code} - {error_detail}")
        except httpx.HTTPError as exc:
            raise ProviderError(f"Vision API request failed: {exc}") from exc

        payload = response.json()
        try:
            content = str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Vision API response is invalid.") from exc

        data = _parse_vision_content(content)
        return VisionTextResult(
            caption=str(data.get("caption") or ""),
            ocr_text=str(data.get("ocr_text") or ""),
            structured_summary=str(data.get("structured_summary") or ""),
            metadata={
                "provider": "http",
                "model": self._model,
                "mimeType": mime_type,
                "fileSize": len(normalized.image_bytes),
                "imageTokens": _extract_image_tokens(payload),
                "maxImageSide": self._max_image_side,
            },
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


_ALLOWED_IMAGE_MIMES = frozenset({
    "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "image/bmp",
})


def _parse_vision_json(content: str) -> dict:
    """解析 Vision API JSON 输出，兼容少量 fenced code 包裹。"""
    cleaned = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", cleaned)
    if fenced:
        cleaned = fenced.group(1)
    else:
        first = cleaned.find("{")
        last = cleaned.rfind("}")
        if first != -1 and last > first:
            cleaned = cleaned[first : last + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Vision API response is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ProviderError("Vision API response must be a JSON object.")
    return data


def _parse_vision_content(content: str) -> dict:
    """解析模型输出；非 JSON 时降级为纯文本摘要以保证图片可检索。"""
    try:
        return _parse_vision_json(content)
    except ProviderError:
        fallback_text = content.strip()
        if not fallback_text:
            raise
        return {
            "caption": fallback_text,
            "ocr_text": "",
            "structured_summary": fallback_text,
        }


def _normalize_request(request: VisionTextRequest | bytes) -> VisionTextRequest:
    """兼容旧 bytes 调用，并为 Provider 内部统一请求形态。"""
    if isinstance(request, VisionTextRequest):
        return request
    return VisionTextRequest(file_name="uploaded-image", mime_type=None, image_bytes=request)


def _resolve_mime_type(file_name: str, mime_type: str | None) -> str:
    """解析图片 MIME；缺失时按扩展名推断，默认使用 JPEG。不在白名单内则拒绝。"""
    resolved = mime_type
    if not resolved:
        guessed, _ = mimetypes.guess_type(file_name)
        resolved = guessed
    if not resolved:
        resolved = "image/jpeg"
    if resolved.lower() not in _ALLOWED_IMAGE_MIMES:
        raise ProviderError(f"Unsupported image MIME type: {resolved}")
    return resolved.lower()


def _extract_image_tokens(payload: dict) -> int | None:
    """从小米/OpenAI-compatible usage 中提取图片 token 数。"""
    details = payload.get("usage", {}).get("prompt_tokens_details")
    if isinstance(details, dict):
        image_tokens = details.get("image_tokens")
        if isinstance(image_tokens, int):
            return image_tokens
    return None
