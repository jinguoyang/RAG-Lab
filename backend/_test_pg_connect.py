"""Quick PG connection and migration test."""
import sys
sys.path.insert(0, ".")

from app.core.config import get_settings
from app.core.database import get_engine
import sqlalchemy as sa

s = get_settings()
print(f"DB URL: {s.database_url}")

e = get_engine()
print(f"Dialect: {e.dialect.name}")

with e.connect() as conn:
    result = conn.execute(sa.text("SELECT version()"))
    print(f"PG Version: {result.scalar()}")

    # Check current alembic version
    try:
        result = conn.execute(sa.text("SELECT version_num FROM alembic_version"))
        versions = [row[0] for row in result]
        print(f"Alembic version: {versions}")
    except Exception as ex:
        print(f"No alembic_version table: {ex}")

    # Check if tables exist
    result = conn.execute(sa.text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' ORDER BY table_name
    """))
    tables = [row[0] for row in result]
    print(f"Tables ({len(tables)}): {tables[:10]}...")

    # Check column types for users table
    result = conn.execute(sa.text("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'users' AND column_name IN ('user_id', 'created_by')
        ORDER BY column_name
    """))
    print("users table UUID columns:")
    for row in result:
        print(f"  {row[0]}: {row[1]}({row[2]})")

    # Check JSONB vs JSON
    result = conn.execute(sa.text("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE data_type IN ('jsonb', 'json')
        ORDER BY table_name, column_name
        LIMIT 10
    """))
    print("JSON columns (first 10):")
    for row in result:
        print(f"  {row[0]}.{row[1]}: {row[2]}")
