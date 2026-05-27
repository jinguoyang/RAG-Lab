"""平台 API 客户端。"""
import httpx


class PlatformClient:
    """Reserved for future platform API calls (e.g., RAG queries)."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"}
