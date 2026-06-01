"""初始化 LangGraph PostgreSQL Checkpoint 表。

用法:
    python backend/scripts/setup_langgraph_checkpoints.py
    python backend/scripts/setup_langgraph_checkpoints.py --check   # 仅检查配置，不执行 setup
"""
from pathlib import Path
import argparse
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _to_psycopg_dsn(url: str | None) -> str | None:
    """将 SQLAlchemy DSN (postgresql+psycopg://) 转为 psycopg 直连 DSN (postgresql://)。"""
    if not url:
        return None
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化 LangGraph PostgreSQL Checkpoint 表")
    parser.add_argument("--check", action="store_true", help="仅检查配置和 DSN 转换，不执行 setup")
    args = parser.parse_args()

    from app.core.config import get_settings  # noqa: E402
    from app.services.agent_runtime.checkpoint_service import create_checkpointer  # noqa: E402

    settings = get_settings()
    raw_url = settings.agent_runtime_checkpoint_database_url or settings.database_url
    database_url = _to_psycopg_dsn(raw_url)
    if not database_url:
        print("ERROR: 未配置数据库 URL，请设置 RAG_LAB_DATABASE_URL 或 RAG_LAB_AGENT_RUNTIME_CHECKPOINT_DATABASE_URL")
        sys.exit(1)

    host_info = database_url.split("@")[1] if "@" in database_url else database_url
    print(f"Target: {host_info}")

    if args.check:
        print("--check 模式：仅验证 DSN 转换和配置，不执行 setup。")
        print(f"DSN: postgresql://***@{host_info}")
        print("注意：不测试数据库连接。")
        sys.exit(0)

    with create_checkpointer(backend="postgres", database_url=database_url) as checkpointer:
        checkpointer.setup()
    print("LangGraph PostgreSQL Checkpoint 表初始化完成。")


if __name__ == "__main__":
    main()
