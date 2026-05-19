"""验证文本预览 API 的导入和路由注册。"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import DTOs
from app.schemas.library import (
    LibraryTextPreviewResponse,
    LibraryFullTextResponse,
    LibraryParsedChunkDTO,
    LibraryParsedChunksResponse,
)

# Import service function
from app.services.library_service import get_document_text

# Import route module to trigger router registration
from app.api.routes.library import router


def main() -> None:
    # Check DTO fields
    preview = LibraryTextPreviewResponse(text="hello", truncated=False, fullLength=5)
    assert preview.text == "hello"
    assert preview.truncated is False
    assert preview.fullLength == 5

    full = LibraryFullTextResponse(text="full text")
    assert full.text == "full text"

    chunk = LibraryParsedChunkDTO(content="chunk", tokenCount=10)
    assert chunk.content == "chunk"
    assert chunk.tokenCount == 10
    assert chunk.section is None
    assert chunk.pageNo is None

    chunks_resp = LibraryParsedChunksResponse(chunks=[chunk])
    assert len(chunks_resp.chunks) == 1

    # Check route is registered
    route_paths = {getattr(route, "path", "") for route in router.routes}
    text_route = any(p.endswith("/{document_id}/text") for p in route_paths)
    assert text_route, f"Route ending with /{{document_id}}/text not found in {route_paths}"

    # Check service function is callable
    assert callable(get_document_text)

    print("verify_text_preview_api: PASS")


if __name__ == "__main__":
    main()
