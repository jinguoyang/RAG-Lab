import pytest
from sqlalchemy.engine import make_url

from scripts.ensure_database import (
    ensure_database,
    maintenance_database_url,
    quote_database_identifier,
)


def test_maintenance_database_url_uses_postgres_database():
    url = maintenance_database_url(
        "postgresql://user:pass@db.example.com:5432/ext_training_040936ae"
    )

    assert str(url) == "postgresql://user:***@db.example.com:5432/postgres"


def test_maintenance_database_url_rejects_empty_database_name():
    with pytest.raises(ValueError, match="database name"):
        maintenance_database_url("postgresql://user:pass@localhost:5432/")


def test_quote_database_identifier_rejects_null_byte():
    with pytest.raises(ValueError, match="null byte"):
        quote_database_identifier(make_url("postgresql://user:pass@localhost/postgres"), "bad\x00db")


def test_ensure_database_creates_database_when_missing():
    connection = FakeConnection(exists=False)

    ensure_database(
        "postgresql://user:pass@localhost:5432/ext_training_040936ae",
        engine_factory=lambda *args, **kwargs: FakeEngine(connection, args, kwargs),
    )

    assert connection.statements == [
        ("SELECT 1 FROM pg_database WHERE datname = :database_name", {"database_name": "ext_training_040936ae"}),
        ("CREATE DATABASE ext_training_040936ae", None),
    ]


def test_ensure_database_does_not_create_existing_database():
    connection = FakeConnection(exists=True)

    ensure_database(
        "postgresql://user:pass@localhost:5432/ext_training_040936ae",
        engine_factory=lambda *args, **kwargs: FakeEngine(connection, args, kwargs),
    )

    assert connection.statements == [
        ("SELECT 1 FROM pg_database WHERE datname = :database_name", {"database_name": "ext_training_040936ae"}),
    ]


class FakeEngine:
    def __init__(self, connection, args, kwargs):
        self.connection = connection
        self.args = args
        self.kwargs = kwargs

    def connect(self):
        return self.connection

    def dispose(self):
        pass


class FakeConnection:
    def __init__(self, exists):
        self.exists = exists
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        self.statements.append((str(statement), params))
        return FakeResult(self.exists)


class FakeResult:
    def __init__(self, exists):
        self.exists = exists

    def scalar(self):
        return 1 if self.exists else None
