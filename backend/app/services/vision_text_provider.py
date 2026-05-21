"""VisionTextProvider：图片视觉文本抽取 Provider 抽象与工厂。"""

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
        # TODO: B-219 - implement HTTP vision API call
        raise NotImplementedError


def get_vision_text_provider(settings: Settings | None = None) -> VisionTextProvider:
    """根据配置创建 VisionTextProvider 实例。"""
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()
    provider_type = settings.vision_text_provider
    if provider_type == "local":
        return LocalVisionTextProvider()
    return HttpVisionTextProvider(settings)
