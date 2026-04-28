"""导出 FastAPI OpenAPI Schema，供发布验收和接口联调留档。"""

from pathlib import Path
import json
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app  # noqa: E402


def main() -> None:
    """生成格式化后的 OpenAPI JSON 文件。"""
    output_path = ROOT_DIR / "docs/06-发布与运维/openapi.json"
    schema = create_app().openapi()
    output_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI schema exported: {output_path}")


if __name__ == "__main__":
    main()
