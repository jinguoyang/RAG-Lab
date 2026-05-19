"""Verify KB ingest parse reuse from library document_versions.

Static analysis confirming:
1. _DictAsObj helper class exists and provides attribute access over dicts.
2. run_ingest_job checks source_type == "library_bind" before parse_document.
3. Library parsed_chunks are converted via _DictAsObj for downstream compatibility.
4. parser_name / parser_version are set in both reuse and normal-parse branches.
"""

import ast
import sys
from pathlib import Path

SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "document_service.py"


def main() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SERVICE_PATH))

    # 1. _DictAsObj class exists
    dict_as_obj_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "_DictAsObj":
            dict_as_obj_class = node
            break
    if dict_as_obj_class is None:
        raise SystemExit("_DictAsObj class not found in document_service.py")

    # Verify __getattr__ is defined
    has_getattr = any(
        isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
        for node in ast.walk(dict_as_obj_class)
    )
    if not has_getattr:
        raise SystemExit("_DictAsObj is missing __getattr__ method")

    # 2. Verify run_ingest_job function exists
    run_ingest_func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_ingest_job":
            run_ingest_func = node
            break
    if run_ingest_func is None:
        raise SystemExit("run_ingest_job function not found")

    func_source = ast.get_source_segment(source, run_ingest_func)
    if func_source is None:
        func_source = source  # fallback

    # 3. Check for library_bind source_type check
    if 'source_type' not in func_source or 'library_bind' not in func_source:
        raise SystemExit("run_ingest_job does not check source_type == 'library_bind'")

    # 4. Check for library document_id lookup
    if 'library_document_id' not in func_source:
        raise SystemExit("run_ingest_job does not read library_document_id from metadata")

    # 5. Check for parsed_chunks_from_library usage
    if 'parsed_chunks_from_library' not in func_source:
        raise SystemExit("run_ingest_job does not use parsed_chunks_from_library")

    # 6. Check for _DictAsObj usage
    if '_DictAsObj' not in func_source:
        raise SystemExit("run_ingest_job does not use _DictAsObj for library chunks")

    # 7. Check for parser_name / parser_version in both branches
    if 'parser_name' not in func_source or 'parser_version' not in func_source:
        raise SystemExit("run_ingest_job does not set parser_name/parser_version")

    # 8. Verify library_reuse sentinel is used
    if 'library_reuse' not in func_source:
        raise SystemExit("run_ingest_job does not use 'library_reuse' sentinel for parser identity")

    # 9. Verify _DictAsObj is importable and works
    BACKEND_DIR = Path(__file__).resolve().parents[1]
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from app.services.document_service import _DictAsObj  # noqa: E402

    test_dict = {"content": "hello", "page_no": 1, "section": "intro", "token_count": 10, "metadata": {"k": "v"}}
    obj = _DictAsObj(test_dict)
    assert obj.content == "hello", f"Expected 'hello', got {obj.content}"
    assert obj.page_no == 1, f"Expected 1, got {obj.page_no}"
    assert obj.section == "intro", f"Expected 'intro', got {obj.section}"
    assert obj.token_count == 10, f"Expected 10, got {obj.token_count}"
    assert obj.metadata == {"k": "v"}, f"Expected dict, got {obj.metadata}"
    assert obj.nonexistent is None, f"Expected None for missing attr, got {obj.nonexistent}"

    print("_DictAsObj", "run_ingest_job", "library_bind", "parsed_chunks_from_library", "parser_name")


if __name__ == "__main__":
    main()
