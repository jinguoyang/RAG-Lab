"""确保外部培训应用使用的 PostgreSQL database 已存在。"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url

from app.core.config import get_settings


def maintenance_database_url(database_url: str) -> URL:
    """生成连接维护库的 URL，用于在目标库不存在时执行 CREATE DATABASE。"""
    url = make_url(database_url)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("Only PostgreSQL database URLs are supported.")
    if not url.database:
        raise ValueError("PostgreSQL database name is required.")
    return url.set(database="postgres")


def quote_database_identifier(url: URL, database_name: str) -> str:
    """按 PostgreSQL 方言引用 database 标识符，避免特殊字符导致 SQL 语法错误。"""
    if "\x00" in database_name:
        raise ValueError("PostgreSQL database name cannot contain a null byte.")

    dialect = url.get_dialect()()
    return dialect.identifier_preparer.quote(database_name)


def ensure_database(
    database_url: str,
    engine_factory: Callable[..., Engine] = create_engine,
) -> None:
    """检查目标 database 是否存在，不存在则在同一实例上创建。"""
    target_url = make_url(database_url)
    database_name = target_url.database
    maintenance_url = maintenance_database_url(database_url)
    quoted_database_name = quote_database_identifier(maintenance_url, database_name)

    engine = engine_factory(
        maintenance_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": database_name},
            ).scalar()
            if exists:
                print(f"Database '{database_name}' already exists.")
                return

            connection.execute(text(f"CREATE DATABASE {quoted_database_name}"))
            print(f"Database '{database_name}' created.")
    finally:
        engine.dispose()


def main() -> None:
    """命令行入口，读取 .env 中的 EXT_TRAINING_DATABASE_URL 并确保库存在。"""
    settings = get_settings()
    ensure_database(settings.database_url)


if __name__ == "__main__":
    main()
