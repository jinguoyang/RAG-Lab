# MarkItDown DOCX/XLSX Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入 MarkItDown 作为 DOCX/XLSX 解析后端，让上传的 Word 和 Excel 文件能稳定转换为 Markdown，再复用现有 Markdown 结构化切块链路。

**Architecture:** 保留 `parse_document()` 作为唯一入口，新增一个很薄的 MarkItDown 适配层，只负责把 DOCX/XLSX 二进制转换为 Markdown 文本。现有 `_parse_markdown()`、`_blocks_to_chunks()`、IngestJob、Chunk、索引副本和权限过滤链路继续复用，避免把解析器替换扩散到入库主流程。

**Tech Stack:** FastAPI, SQLAlchemy Core, existing `document_parsing.py`, MarkItDown, pytest-style verification scripts, Conda environment from `backend/environment.yml`.

---

## File Structure

- Modify: `backend/requirements.txt`，增加 MarkItDown 依赖，固定到当前可验证主版本范围。
- Modify: `backend/app/services/document_parsing.py`，新增 MarkItDown 适配函数，并让 `.docx` 和 `.xlsx` 走统一 Markdown 解析路径。
- Create: `backend/scripts/verify_markitdown_docx_xlsx_parse.py`，建立本地可重复的解析验收脚本。
- Modify: `docs/04-迭代与交付/产品待办清单.md`，实现完成后把 B-130 状态从 Ready 更新为 Done，并在来源或说明中记录验证脚本。
- Do not modify UI files in this plan. The verification script generates the XLSX fixture at runtime, so no binary Excel sample is added to `docs/examples/`.

## Task 1: Add MarkItDown Dependency Guard

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add the dependency**

Edit `backend/requirements.txt` near the parser/runtime dependencies:

```text
pypdf>=6.0,<7.0
markitdown>=0.1,<0.2
openpyxl>=3.1,<4.0
python-docx>=1.1,<2.0
```

Keep `pypdf` because PDF remains on the current parser until a separate comparison task chooses otherwise. Add `openpyxl` and `python-docx` explicitly because MarkItDown uses format-specific packages for Office conversions, and hidden transitive dependencies make rebuild failures harder to diagnose.

- [ ] **Step 2: Rebuild or refresh the backend environment**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m pip install -r requirements.txt
```

Expected: command exits `0` and installs or confirms `markitdown`, `openpyxl`, and `python-docx`.

- [ ] **Step 3: Verify imports**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
conda run -n rag-lab python -c "from markitdown import MarkItDown; import openpyxl, docx; print('markitdown imports ok')"
```

Expected output includes:

```text
markitdown imports ok
```

## Task 2: Write Failing Parser Verification

**Files:**
- Create: `backend/scripts/verify_markitdown_docx_xlsx_parse.py`

- [ ] **Step 1: Create the verification script**

Create `backend/scripts/verify_markitdown_docx_xlsx_parse.py`:

```python
"""Verify MarkItDown-backed DOCX/XLSX parsing.

The script keeps Office parser checks local and deterministic. It creates a
small XLSX fixture at runtime so the repository does not need a binary test
file for the first MarkItDown integration.
"""

from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
EXAMPLE_DIR = ROOT_DIR / "docs" / "examples"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.document_parsing import parse_document  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """Fail with a clear message for parser acceptance gaps."""
    if not condition:
        raise AssertionError(message)


def _example_docx() -> Path:
    """Use the existing stable DOCX sample as the Word parser fixture."""
    matches = sorted(EXAMPLE_DIR.glob("*.docx"))
    _assert(bool(matches), "docs/examples 缺少 docx 样例文件")
    return matches[0]


def _create_xlsx_fixture(path: Path) -> None:
    """Create a minimal workbook with headers and business text."""
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "物料清单"
    sheet.append(["物料编码", "物料名称", "处理策略"])
    sheet.append(["M-001", "呆滞电源模块", "优先调拨"])
    sheet.append(["M-002", "备品电缆", "季度复核"])
    workbook.save(path)


def verify_docx_uses_markdown_chunks() -> None:
    """DOCX should parse through MarkItDown and preserve meaningful text."""
    path = _example_docx()
    parsed = parse_document(path.name, None, path.read_bytes(), chunk_size=700, chunk_overlap=80)
    contents = "\n".join(chunk.content for chunk in parsed.chunks)

    _assert(parsed.parser_name == "markitdown_docx", "DOCX 应使用 markitdown_docx parserName")
    _assert(parsed.chunks, "DOCX 未生成 Chunk")
    _assert(any(chunk.section for chunk in parsed.chunks), "DOCX Chunk 应包含章节或段落定位")
    _assert("迁移" in contents or "方案" in contents, "DOCX 样例核心文本未进入 Chunk")


def verify_xlsx_uses_markdown_chunks() -> None:
    """XLSX should parse table-like content into searchable chunks."""
    with TemporaryDirectory() as tmp_dir:
        xlsx_path = Path(tmp_dir) / "markitdown-sample.xlsx"
        _create_xlsx_fixture(xlsx_path)
        parsed = parse_document(xlsx_path.name, None, xlsx_path.read_bytes(), chunk_size=700, chunk_overlap=80)

    contents = "\n".join(chunk.content for chunk in parsed.chunks)
    _assert(parsed.parser_name == "markitdown_xlsx", "XLSX 应使用 markitdown_xlsx parserName")
    _assert(parsed.chunks, "XLSX 未生成 Chunk")
    _assert("物料编码" in contents, "XLSX 表头未进入 Chunk")
    _assert("呆滞电源模块" in contents, "XLSX 单元格内容未进入 Chunk")
    _assert(all(chunk.metadata.get("sourceExtension") == ".xlsx" for chunk in parsed.chunks), "XLSX metadata 扩展名错误")


def main() -> None:
    """Run local MarkItDown parser acceptance checks."""
    verify_docx_uses_markdown_chunks()
    verify_xlsx_uses_markdown_chunks()
    print("MarkItDown DOCX/XLSX parse verification passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script and confirm it fails before implementation**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
conda run -n rag-lab python backend\scripts\verify_markitdown_docx_xlsx_parse.py
```

Expected before implementation: FAIL because `.xlsx` currently returns `UNSUPPORTED_FILE_TYPE`, and `.docx` currently uses `docx_python_docx`.

## Task 3: Add MarkItDown Adapter

**Files:**
- Modify: `backend/app/services/document_parsing.py`

- [ ] **Step 1: Add a conversion helper**

Add imports near the top:

```python
from tempfile import NamedTemporaryFile
```

Add this helper after `_parse_markdown()`:

```python
def _parse_markitdown_office(file_name: str, file_bytes: bytes) -> list[dict]:
    """Convert Office files to Markdown text through MarkItDown before chunking."""
    suffix = PurePath(file_name).suffix.lower()
    try:
        from markitdown import MarkItDown

        with NamedTemporaryFile(suffix=suffix, delete=True) as temp_file:
            temp_file.write(file_bytes)
            temp_file.flush()
            result = MarkItDown().convert(temp_file.name)
        markdown_text = _normalize_text(result.text_content or "")
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("MARKITDOWN_PARSE_FAILED", "Office document conversion failed.") from exc

    if not markdown_text:
        raise DocumentParseError("PARSE_EMPTY_CONTENT", "Parsed document has no extractable text.")
    return _parse_structured_text_blocks(markdown_text, "Office paragraph")
```

This helper writes to a temporary file because MarkItDown’s stable public API is path-oriented. It raises the project’s existing `DocumentParseError` so IngestJob failure handling remains unchanged.

- [ ] **Step 2: Route DOCX and XLSX through the helper**

Change the relevant part of `parse_document()` to:

```python
    elif extension == ".pdf":
        blocks = _parse_pdf(file_bytes)
        parser_name = "pdf_pypdf"
    elif extension == ".docx":
        blocks = _parse_markitdown_office(normalized_name, file_bytes)
        parser_name = "markitdown_docx"
    elif extension == ".xlsx":
        blocks = _parse_markitdown_office(normalized_name, file_bytes)
        parser_name = "markitdown_xlsx"
```

Do not add `.xls` in this task. Legacy binary Excel has different dependency and failure characteristics; add it only after a sample and explicit acceptance rule exist.

- [ ] **Step 3: Keep the old DOCX helper temporarily**

Leave `_parse_docx()` in place for this task, but remove its call from `parse_document()`. After the MarkItDown path passes verification, decide in a separate cleanup step whether to delete `_parse_docx()` or keep it as an explicit fallback. If kept as fallback, add a test proving fallback behavior before wiring it.

## Task 4: Verify MarkItDown Parser Behavior

**Files:**
- Test: `backend/scripts/verify_markitdown_docx_xlsx_parse.py`
- Test: `backend/scripts/verify_sprint19_real_parse.py`

- [ ] **Step 1: Run the new MarkItDown verification**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
conda run -n rag-lab python backend\scripts\verify_markitdown_docx_xlsx_parse.py
```

Expected output:

```text
MarkItDown DOCX/XLSX parse verification passed.
```

- [ ] **Step 2: Run the existing real parse verification**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
conda run -n rag-lab python backend\scripts\verify_sprint19_real_parse.py
```

Expected output:

```text
Sprint 19 real parse verification passed.
```

If this fails because the old script expects DOCX parser name `docx_python_docx`, update the expectation to require non-placeholder parser output and meaningful section metadata, not a specific parser implementation name.

- [ ] **Step 3: Compile backend code**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
```

Expected: command exits `0` with no syntax errors.

## Task 5: Document Status and Acceptance

**Files:**
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Update B-130 status**

Change B-130 from:

```markdown
| B-130 | E24 | 技术 | 评估 MarkItDown 作为 DOCX/XLSX 解析试点，输出 Markdown 后复用现有 Markdown 切块 | 文档解析能力增强计划、P06 上传解析链路 | P1 | 内部增强 | Ready | Codex |
```

to:

```markdown
| B-130 | E24 | 技术 | 引入 MarkItDown 作为 DOCX/XLSX 解析试点，输出 Markdown 后复用现有 Markdown 切块 | `verify_markitdown_docx_xlsx_parse.py`、P06 上传解析链路 | P1 | 内部增强 | Done | Codex |
```

- [ ] **Step 2: Run documentation diff check**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
git diff --check -- backend\requirements.txt backend\app\services\document_parsing.py backend\scripts\verify_markitdown_docx_xlsx_parse.py docs\04-迭代与交付\产品待办清单.md
```

Expected: no whitespace errors. Line-ending warnings are acceptable if they match the repository’s current Git configuration.

## Task 6: Commit

**Files:**
- Stage only files changed for this plan.

- [ ] **Step 1: Review diff**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
git diff -- backend\requirements.txt backend\app\services\document_parsing.py backend\scripts\verify_markitdown_docx_xlsx_parse.py docs\04-迭代与交付\产品待办清单.md
```

Expected: diff only contains MarkItDown dependency, parser routing, verification script, and B-130 status update.

- [ ] **Step 2: Stage the implementation files**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
git add backend\requirements.txt backend\app\services\document_parsing.py backend\scripts\verify_markitdown_docx_xlsx_parse.py docs\04-迭代与交付\产品待办清单.md
```

- [ ] **Step 3: Commit**

Run:

```powershell
git commit -m "feat: add markitdown office parsing"
```

Expected: commit succeeds and includes only the files listed above.

## Self-Review Notes

- Spec coverage: B-130 is covered by dependency setup, adapter implementation, DOCX/XLSX verification, existing parser regression, and backlog status update.
- Scope control: PDF remains on `pypdf`; MinerU remains in B-132 and is not part of this implementation plan.
- Parser boundary: all ingestion callers continue to use `parse_document()`, so API, Worker, Chunk, and index sync contracts remain unchanged.
- Risk: MarkItDown output shape may vary by document. The acceptance checks focus on searchable text, table headers, cell content, and section metadata rather than byte-for-byte Markdown.
