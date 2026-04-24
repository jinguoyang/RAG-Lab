from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _database_url() -> str:
    """读取迁移数据库地址，确保迁移和应用运行使用同一套配置入口。"""
    settings = get_settings()
    if settings.database_url:
        return settings.database_url

    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url:
        return configured_url

    raise RuntimeError(
        "Database URL is required. Set DATABASE_URL or RAG_LAB_DATABASE_URL before running migrations."
    )


def run_migrations_offline() -> None:
    """离线生成 SQL，用于审查迁移内容而不连接数据库。"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线执行迁移，连接池仅用于本次命令生命周期。"""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
