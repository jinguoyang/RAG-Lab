"""Sprint 38 综合验证脚本。"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

def check_imports():
    """验证所有新增模块可导入。"""
    from app.services.permission_service import has_library_permission
    from app.services.library_service import batch_action, get_library_stats, _get_error_suggestion
    from app.schemas.library import BatchActionRequest, BatchActionResponse, LibraryStatsResponse
    from app.api.routes.library import router
    print("  [OK] All imports successful")

def check_permission_function():
    """验证权限函数签名。"""
    from app.services.permission_service import has_library_permission
    import inspect
    sig = inspect.signature(has_library_permission)
    params = list(sig.parameters.keys())
    assert "session" in params, "Missing 'session' parameter"
    assert "current_user" in params, "Missing 'current_user' parameter"
    assert "permission_code" in params, "Missing 'permission_code' parameter"
    assert "document_owner_id" in params, "Missing 'document_owner_id' parameter"
    print("  [OK] has_library_permission signature correct")

def check_batch_function():
    """验证批量操作函数签名。"""
    from app.services.library_service import batch_action
    import inspect
    sig = inspect.signature(batch_action)
    params = list(sig.parameters.keys())
    assert "session" in params
    assert "current_user" in params
    assert "document_ids" in params
    assert "action" in params
    print("  [OK] batch_action signature correct")

def check_stats_function():
    """验证统计函数签名。"""
    from app.services.library_service import get_library_stats
    import inspect
    sig = inspect.signature(get_library_stats)
    params = list(sig.parameters.keys())
    assert "session" in params
    assert "current_user" in params
    print("  [OK] get_library_stats signature correct")

def check_schemas():
    """验证 DTO 定义。"""
    from app.schemas.library import BatchActionRequest, BatchActionResponse, LibraryStatsResponse
    # BatchActionRequest
    req = BatchActionRequest(documentIds=["a", "b"], action="delete")
    assert len(req.documentIds) == 2
    assert req.action == "delete"
    # LibraryStatsResponse
    stats = LibraryStatsResponse(totalDocuments=10, todayUploads=2, pendingParse=3)
    assert stats.totalDocuments == 10
    print("  [OK] Schemas validate correctly")

def check_routes():
    """验证路由注册。"""
    from app.api.routes.library import router
    paths = [route.path for route in router.routes]
    has_batch = any(p.endswith("/batch-actions") for p in paths)
    has_stats = any(p.endswith("/stats") for p in paths)
    assert has_batch, "Missing /batch-actions route"
    assert has_stats, "Missing /stats route"
    print("  [OK] Routes registered: /batch-actions, /stats")

def check_tables():
    """验证表定义。"""
    from app.tables import library_parse_jobs
    column_names = [col.name for col in library_parse_jobs.columns]
    assert "error_detail" in column_names, "Missing error_detail column"
    print("  [OK] library_parse_jobs has error_detail column")

def main():
    print("Sprint 38 Verification")
    print("=" * 40)
    checks = [
        ("Imports", check_imports),
        ("Permission function", check_permission_function),
        ("Batch function", check_batch_function),
        ("Stats function", check_stats_function),
        ("Schemas", check_schemas),
        ("Routes", check_routes),
        ("Tables", check_tables),
    ]
    passed = 0
    failed = 0
    for name, check in checks:
        try:
            print(f"\n--- {name} ---")
            check()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

    print("\n" + "=" * 40)
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    print("All checks passed!")

if __name__ == "__main__":
    main()
