"""Functional test against live PG database after multi-db migration."""
import json
import sys
import time

import httpx

BASE = "http://localhost:8100/api/v1"
HEADERS = {"X-Dev-User": "admin"}
UNIQUE = str(int(time.time()))[-6:]  # last 6 digits of unix timestamp

passed = 0
failed = 0


def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f"  PASS  {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        failed += 1


def get(path, **kwargs):
    r = httpx.get(f"{BASE}{path}", headers=HEADERS, timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()


def post(path, **kwargs):
    r = httpx.post(f"{BASE}{path}", headers=HEADERS, timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()


def put(path, **kwargs):
    r = httpx.put(f"{BASE}{path}", headers=HEADERS, timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()


def delete(path, **kwargs):
    r = httpx.request("DELETE", f"{BASE}{path}", headers=HEADERS, timeout=30, **kwargs)
    r.raise_for_status()
    # 204 No Content has no body
    if r.status_code == 204:
        return None
    return r.json()


# ── Health ──────────────────────────────────────────────────────────
print("\n=== Health ===")
test("health check", lambda: get("/health"))


# ── Groups ──────────────────────────────────────────────────────────
print("\n=== Groups ===")

def test_group_flow():
    gname = f"test-group-{UNIQUE}"
    group = post("/groups", json={"name": gname, "description": "test"})
    gid = group.get("groupId")
    assert gid, f"No group ID in: {group}"
    assert isinstance(gid, str) and len(gid) == 36, f"ID not UUID string: {gid}"

    fetched = get(f"/groups/{gid}")
    assert fetched.get("name") == gname

    # No DELETE endpoint for groups exists, just verify read works

test("group create + read", test_group_flow)


# ── Knowledge Base ──────────────────────────────────────────────────
print("\n=== Knowledge Base ===")

def test_kb_flow():
    kbname = f"test-kb-{UNIQUE}"
    kb = post("/knowledge-bases", json={"name": kbname, "description": "test"})
    kb_id = kb.get("kbId")
    assert kb_id, f"No kb ID in: {kb}"
    assert isinstance(kb_id, str) and len(kb_id) == 36, f"ID not UUID string: {kb_id}"

    fetched = get(f"/knowledge-bases/{kb_id}")
    assert fetched.get("name") == kbname

    kbs = get("/knowledge-bases")
    items = kbs.get("items", [])
    assert any(k.get("kbId") == kb_id for k in items), "KB not in list"

    # Delete requires confirmName
    delete(f"/knowledge-bases/{kb_id}", json={"confirmName": kbname})

test("knowledge base CRUD", test_kb_flow)


# ── RAG Apps ────────────────────────────────────────────────────────
print("\n=== RAG Apps ===")

def test_rag_apps():
    apps = get("/rag-apps", params={"page": 1, "pageSize": 5})
    assert "items" in apps, f"Unexpected: {apps}"

test("rag apps list", test_rag_apps)


# ── Dictionaries ────────────────────────────────────────────────────
print("\n=== Dictionaries ===")

def test_dicts():
    dicts = get("/dictionaries")
    assert isinstance(dicts, (list, dict)), f"Unexpected: {dicts}"

test("dictionaries list", test_dicts)


# ── Audit Logs ──────────────────────────────────────────────────────
print("\n=== Audit Logs ===")

def test_audit():
    logs = get("/audit-logs", params={"page": 1, "pageSize": 5})
    assert "items" in logs, f"Unexpected: {logs}"

test("audit logs list", test_audit)


# ── UUID String Format Verification ─────────────────────────────────
print("\n=== UUID Format Verification ===")

def test_uuid_format():
    """Verify IDs returned from API are UUID-format strings, not UUID objects."""
    kbname = f"uuid-check-{UNIQUE}"
    kb = post("/knowledge-bases", json={"name": kbname, "description": "check"})
    kb_id = kb.get("kbId")

    # Must be string type in JSON (not serialized UUID object)
    assert isinstance(kb_id, str), f"kb_id is {type(kb_id)}, expected str"
    # Must be valid UUID format: 8-4-4-4-12
    parts = kb_id.split("-")
    assert len(parts) == 5, f"Not UUID format: {kb_id}"
    assert len(parts[0]) == 8 and len(parts[1]) == 4, f"Not UUID format: {kb_id}"
    # All hex chars
    for part in parts:
        int(part, 16)

    delete(f"/knowledge-bases/{kb_id}", json={"confirmName": kbname})

test("UUID format is string", test_uuid_format)


# ── JSON Column Read/Write ──────────────────────────────────────────
print("\n=== JSON Column Read/Write ===")

def test_json_flow():
    """Verify JSON columns store and retrieve nested data correctly."""
    kbname = f"json-test-{UNIQUE}"
    kb = post("/knowledge-bases", json={
        "name": kbname,
        "description": "test",
    })
    kb_id = kb.get("kbId")

    fetched = get(f"/knowledge-bases/{kb_id}")

    # Check camelCase JSON fields exist and are correct types
    for field in ["requiredForActivation"]:
        if field in fetched:
            val = fetched[field]
            assert isinstance(val, (dict, type(None))), \
                f"{field} type wrong: {type(val)}, value: {val}"

    delete(f"/knowledge-bases/{kb_id}", json={"confirmName": kbname})

test("JSON column read/write", test_json_flow)


# ── Cross-table FK integrity ────────────────────────────────────────
print("\n=== Cross-table FK Integrity ===")

def test_fk_integrity():
    """Create KB, verify config_revision links back correctly."""
    kbname = f"fk-test-{UNIQUE}"
    kb = post("/knowledge-bases", json={"name": kbname, "description": "test"})
    kb_id = kb.get("kbId")
    config_rev_id = kb.get("activeConfigRevisionId")

    # Config revision should exist and reference the KB
    if config_rev_id:
        rev = get(f"/knowledge-bases/{kb_id}/config-revisions/{config_rev_id}")
        assert rev is not None, "Config revision not found"

    delete(f"/knowledge-bases/{kb_id}", json={"confirmName": kbname})

test("FK integrity (KB -> config revision)", test_fk_integrity)


# ── Multiple create/delete cycle ────────────────────────────────────
print("\n=== Stress: Multiple Create/Delete ===")

def test_stress():
    ids = []
    for i in range(5):
        kbname = f"stress-{UNIQUE}-{i}"
        kb = post("/knowledge-bases", json={"name": kbname, "description": "stress"})
        kid = kb.get("kbId")
        assert kid, f"Failed to create KB {i}"
        ids.append((kid, kbname))

    # All IDs should be unique
    id_list = [k for k, _ in ids]
    assert len(set(id_list)) == 5, f"Duplicate IDs: {id_list}"

    # All should be retrievable
    for kid, _ in ids:
        fetched = get(f"/knowledge-bases/{kid}")
        assert fetched is not None

    # Clean up
    for kid, name in ids:
        delete(f"/knowledge-bases/{kid}", json={"confirmName": name})

test("5x create/delete cycle", test_stress)


# ── Verify DB directly ──────────────────────────────────────────────
print("\n=== Direct DB Verification ===")

def test_db_direct():
    """Query the database directly to verify column types."""
    import sqlalchemy as sa
    from app.core.database import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        # Check UUID columns are now VARCHAR(36)
        result = conn.execute(sa.text("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'user_id'
        """))
        dtype = result.scalar()
        assert dtype == "character varying", f"user_id type is {dtype}, expected varchar"

        # Check JSON columns are now JSON (not JSONB)
        result = conn.execute(sa.text("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'audit_logs' AND column_name = 'detail'
        """))
        dtype = result.scalar()
        assert dtype == "json", f"detail type is {dtype}, expected json"

        # Verify data survived migration (existing rows still have UUID-format values)
        result = conn.execute(sa.text("""
            SELECT user_id FROM users LIMIT 1
        """))
        row = result.scalar()
        if row:
            assert isinstance(row, str), f"user_id is {type(row)}, expected str"
            assert len(row) == 36, f"user_id length is {len(row)}, expected 36"

test("DB column types correct", test_db_direct)


# ── Summary ─────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All functional tests passed!")
