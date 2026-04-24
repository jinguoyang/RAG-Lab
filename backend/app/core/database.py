from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """创建并缓存数据库引擎，保证 API 与迁移共用同一连接配置。"""
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("Database URL is required. Set RAG_LAB_DATABASE_URL or DATABASE_URL.")
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """返回统一 Session 工厂，便于服务层显式控制事务边界。"""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _session_factory


def get_db_session() -> Iterator[Session]:
    """FastAPI 依赖：为单次请求提供数据库会话并在结束时关闭。"""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
