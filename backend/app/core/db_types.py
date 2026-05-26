"""数据库方言适配层。

遵循项目 Provider 接口模式（参考 QARunProviders、ObjectStorageProvider），
封装 PostgreSQL / MySQL 的方言差异，使 tables.py 和 service 层无需感知底层数据库。
"""
from __future__ import annotations

from typing import Protocol
from uuid import uuid4

import sqlalchemy as sa


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------

def new_id() -> str:
    """生成全局唯一 ID（UUID v4 字符串），替代各处 uuid4() 调用。"""
    return str(uuid4())


# ---------------------------------------------------------------------------
# DialectAdapter 接口
# ---------------------------------------------------------------------------

class DialectAdapter(Protocol):
    """数据库方言适配器接口。

    每个属性返回一个可直接用于 sa.Column() 的 SQLAlchemy 类型实例。
    tables.py 通过此接口获取列类型，不再直接引用 postgresql 模块。
    """

    @property
    def uuid_type(self) -> type[sa.types.TypeEngine]:
        """UUID / 主键列类型。"""
        ...

    @property
    def json_type(self) -> type[sa.types.TypeEngine]:
        """JSON 列类型。"""
        ...

    def json_default(self, value: str = "{}") -> sa.TextClause:
        """JSON 列的 server_default 值。"""
        ...

    def timestamp_default(self) -> sa.TextClause:
        """时间戳列的 server_default 值（如 now() / CURRENT_TIMESTAMP）。"""
        ...

    def supports_partial_index(self) -> bool:
        """是否支持带 WHERE 条件的部分索引。"""
        ...


# ---------------------------------------------------------------------------
# PostgreSQL 实现
# ---------------------------------------------------------------------------

class PostgresAdapter:
    """PostgreSQL 方言适配器。"""

    @property
    def uuid_type(self) -> type[sa.types.TypeEngine]:
        return sa.String(36)

    @property
    def json_type(self) -> type[sa.types.TypeEngine]:
        return sa.JSON

    def json_default(self, value: str = "{}") -> sa.TextClause:
        # value is always a hardcoded literal ("{}" or "[]"), never user input
        _defaults = {"{}": "'{}'", "[]": "'[]'"}
        return sa.text(_defaults.get(value, "'{}'"))

    def timestamp_default(self) -> sa.TextClause:
        return sa.text("now()")

    def supports_partial_index(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# MySQL 实现
# ---------------------------------------------------------------------------

class MySqlAdapter:
    """MySQL 方言适配器。"""

    @property
    def uuid_type(self) -> type[sa.types.TypeEngine]:
        return sa.String(36)

    @property
    def json_type(self) -> type[sa.types.TypeEngine]:
        return sa.JSON

    def json_default(self, value: str = "{}") -> sa.TextClause:
        # MySQL JSON 列不支持 server_default，需在应用层处理
        return sa.text("NULL")

    def timestamp_default(self) -> sa.TextClause:
        return sa.text("CURRENT_TIMESTAMP")

    def supports_partial_index(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------

def get_dialect_adapter(database_url: str | None = None) -> DialectAdapter:
    """根据数据库 URL 返回对应的方言适配器。"""
    if database_url is None:
        from app.core.config import get_settings
        database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("Database URL is required.")

    url = sa.engine.url.make_url(database_url)
    drivername = url.drivername.lower()

    if "mysql" in drivername or "pymysql" in drivername:
        return MySqlAdapter()
    # 默认 PostgreSQL
    return PostgresAdapter()
