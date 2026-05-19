"""测试配置：fixtures 和测试数据库。"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, sessionmaker

# 使用 SQLite in-memory 作为测试数据库
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL, echo=False)

    # SQLite 不支持 JSONB，需要在编译时映射为 JSON
    @event.listens_for(engine, "before_execute")
    def _receive_before_execute(conn, clauseelement, multiparams, params, execution_options):
        pass

    from sqlalchemy import TypeDecorator, String
    from sqlalchemy.dialects.sqlite import JSON

    # 为 SQLite 编译器注册 JSONB -> JSON 映射
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

    @compiles(PG_JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):
        return "JSON"

    # 创建所有表（SQLite in-memory 需要显式创建）
    from app.tables import metadata

    metadata.create_all(engine)
    yield engine
    metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db(engine):
    """每个测试一个独立的数据库 session，测试后回滚。"""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def test_user():
    """模拟当前用户。"""
    from app.schemas.auth import CurrentUserResponse, UserDTO

    user_id = str(uuid4())
    return CurrentUserResponse(
        user=UserDTO(
            userId=user_id,
            username="testuser",
            displayName="Test User",
            email="test@example.com",
            platformRole="user",
            securityLevel="internal",
            status="active",
        ),
        platformPermissions=[],
        visibleKbCount=0,
    )


@pytest.fixture()
def admin_user():
    """模拟管理员用户。"""
    from app.schemas.auth import CurrentUserResponse, UserDTO

    user_id = str(uuid4())
    return CurrentUserResponse(
        user=UserDTO(
            userId=user_id,
            username="admin",
            displayName="Admin User",
            email="admin@example.com",
            platformRole="admin",
            securityLevel="internal",
            status="active",
        ),
        platformPermissions=[],
        visibleKbCount=0,
    )
