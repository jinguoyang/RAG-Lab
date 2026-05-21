from dataclasses import dataclass, field
from io import BytesIO
from pathlib import PurePath
import re
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from app.services.vision_text_provider import get_vision_text_provider


PARSER_VERSION = "sprint19.2"
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 120

CHINESE_NUMBER_PATTERN = r"[一二三四五六七八九十百千万零〇两\d]+"
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
LEGAL_HEADING_RE = re.compile(rf"^(第{CHINESE_NUMBER_PATTERN}([章节条]))\s+(.+)$")
CHINESE_LIST_HEADING_RE = re.compile(r"^([一二三四五六七八九十]+)[、.]\s*(.{1,30})$")
NUMBERED_HEADING_RE = re.compile(r"^(\d+)[、.]\s+(.{1,30})$")
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class ParsedChunk:
    """解析后可直接写入 PostgreSQL Chunk 真值表的文本片段。"""

    content: str
    token_count: int
    section: str | None
    page_no: int | None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    """文档解析结果，保留解析器身份和所有 Chunk。"""

    parser_name: str
    parser_version: str
    source_file_name: str
    mime_type: str | None
    chunks: list[ParsedChunk]


class DocumentParseError(RuntimeError):
    """文档解析失败，调用方应将错误写入 DocumentVersion 和 IngestJob。"""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def parse_document(
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> ParsedDocument:
    """按文件类型解析 txt、md、pdf、docx，并返回结构化 Chunk。"""
    normalized_name = PurePath(file_name).name or "uploaded-document"
    extension = PurePath(normalized_name).suffix.lower()
    if extension == ".txt":
        blocks = _parse_plain_text(file_bytes)
        parser_name = "plain_text"
    elif extension == ".md":
        blocks = _parse_markdown(file_bytes)
        parser_name = "markdown"
    elif extension == ".pdf":
        blocks = _parse_pdf(file_bytes)
        parser_name = "pdf_pypdf"
    elif extension == ".docx":
        blocks = _parse_docx(file_bytes)
        parser_name = "docx_python_docx"
    elif extension in _IMAGE_EXTENSIONS:
        return _parse_image(file_bytes, normalized_name, mime_type, chunk_size, chunk_overlap)
    else:
        raise DocumentParseError("UNSUPPORTED_FILE_TYPE", f"Unsupported file type: {extension or 'unknown'}")

    chunks = _blocks_to_chunks(
        blocks,
        parser_name=parser_name,
        source_extension=extension,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    if not chunks:
        raise DocumentParseError("PARSE_EMPTY_CONTENT", "Parsed document has no extractable text.")
    return ParsedDocument(
        parser_name=parser_name,
        parser_version=PARSER_VERSION,
        source_file_name=normalized_name,
        mime_type=mime_type,
        chunks=chunks,
    )


def _decode_text(file_bytes: bytes) -> str:
    """按常见中文与 UTF-8 编码解析文本文件。"""
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentParseError("TEXT_DECODE_FAILED", "Text file cannot be decoded as UTF-8 or GB18030.")


def _parse_plain_text(file_bytes: bytes) -> list[dict]:
    """解析纯文本，优先识别 Markdown-like 与制度类章节。"""
    text = _normalize_text(_decode_text(file_bytes))
    return _parse_structured_text_blocks(text, "Text paragraph")


def _parse_markdown(file_bytes: bytes) -> list[dict]:
    """解析 Markdown 标题层级，段落 metadata 继承最近标题。"""
    text = _normalize_text(_decode_text(file_bytes))
    return _parse_structured_text_blocks(text, "Markdown paragraph")


def _parse_structured_text_blocks(text: str, fallback_prefix: str) -> list[dict]:
    """解析通用文本章节，未发现标题时回退到段落序号。"""
    blocks: list[dict] = []
    heading_stack: dict[int, str] = {}
    found_heading = False
    buffer: list[str] = []

    def flush_buffer() -> None:
        nonlocal buffer
        content = "\n".join(buffer).strip()
        if content:
            blocks.append({"content": content, "section": _current_section(heading_stack), "page_no": None})
        buffer = []

    for line in text.splitlines():
        stripped = line.strip()
        heading = _detect_text_heading(stripped, allow_list_heading=not bool(heading_stack))
        if heading:
            flush_buffer()
            found_heading = True
            level, title, inline_content = heading
            _set_heading(heading_stack, level, title)
            if inline_content:
                buffer.append(inline_content)
            continue
        if stripped:
            buffer.append(line)
        else:
            flush_buffer()
    flush_buffer()
    if found_heading:
        return blocks
    return [
        {"content": paragraph, "section": f"{fallback_prefix} {index}", "page_no": None}
        for index, paragraph in enumerate(_paragraphs(text), start=1)
    ]


def _detect_text_heading(line: str, allow_list_heading: bool = True) -> tuple[int, str, str] | None:
    """识别 Markdown、章条和谨慎的列表式标题，并拆出同行正文。"""
    if not line:
        return None
    markdown = MARKDOWN_HEADING_RE.match(line)
    if markdown:
        level = len(markdown.group(1))
        title, inline_content = _split_heading_inline_content(markdown.group(2).strip())
        return level, title, inline_content

    legal = LEGAL_HEADING_RE.match(line)
    if legal:
        level = 2 if legal.group(2) == "章" else 3
        title, inline_content = _split_heading_inline_content(line)
        return level, title, inline_content

    if allow_list_heading:
        for pattern in (CHINESE_LIST_HEADING_RE, NUMBERED_HEADING_RE):
            match = pattern.match(line)
            if match and _looks_like_short_heading(match.group(2)):
                return 4, line, ""
    return None


def _split_heading_inline_content(text: str) -> tuple[str, str]:
    """把制度类标题中的标题名和同行正文分开。"""
    legal = LEGAL_HEADING_RE.match(text)
    if legal is None:
        return text, ""
    label = legal.group(1)
    unit = legal.group(2)
    rest = legal.group(3).strip()
    if unit == "章":
        return text, ""

    for delimiter in (" - ", " 1. ", " 1、"):
        if delimiter in rest:
            title, body = rest.split(delimiter, 1)
            return f"{label} {title.strip()}", f"{delimiter.strip()} {body.strip()}".strip()

    parts = rest.split(maxsplit=1)
    if len(parts) == 2 and len(parts[0]) <= 16:
        return f"{label} {parts[0]}", parts[1].strip()
    return text, ""


def _looks_like_short_heading(text: str) -> bool:
    """限制列表式标题识别范围，避免把正文列表项误判为章节。"""
    return not re.search(r"[，。；：:、]", text) and len(text.strip()) <= 20


def _set_heading(heading_stack: dict[int, str], level: int, title: str) -> None:
    """更新当前章节栈，低层级标题会替换其下所有旧标题。"""
    for existing_level in list(heading_stack):
        if existing_level >= level:
            del heading_stack[existing_level]
    heading_stack[level] = title


def _current_section(heading_stack: dict[int, str]) -> str | None:
    """生成展示用章节路径；有章/条时省略文档总标题。"""
    if not heading_stack:
        return None
    levels = sorted(heading_stack)
    if any(level > 1 for level in levels):
        levels = [level for level in levels if level > 1]
    return " > ".join(heading_stack[level] for level in levels)


def _parse_pdf(file_bytes: bytes) -> list[dict]:
    """使用 pypdf 提取 PDF 页文本；复杂版面与 OCR 留到后续版本。"""
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(file_bytes))
        blocks: list[dict] = []
        for page_index, page in enumerate(reader.pages, start=1):
            page_text = _normalize_text(page.extract_text() or "")
            for paragraph in _paragraphs(page_text):
                blocks.append({"content": paragraph, "section": f"Page {page_index}", "page_no": page_index})
        return blocks
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("PDF_PARSE_FAILED", "PDF text extraction failed.") from exc


def _parse_docx(file_bytes: bytes) -> list[dict]:
    """使用标准库读取 docx XML，避免解析链路依赖额外原生包。"""
    try:
        with ZipFile(BytesIO(file_bytes)) as archive:
            document_xml = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as exc:
        raise DocumentParseError("DOCX_PARSE_FAILED", "DOCX text extraction failed.") from exc

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ElementTree.fromstring(document_xml)
    blocks: list[dict] = []
    current_section: str | None = None
    for paragraph in root.findall(".//w:p", namespace):
        text_nodes = paragraph.findall(".//w:t", namespace)
        content = _normalize_text("".join(node.text or "" for node in text_nodes))
        if not content:
            continue
        style_node = paragraph.find("./w:pPr/w:pStyle", namespace)
        style_value = style_node.attrib.get(f"{{{namespace['w']}}}val", "") if style_node is not None else ""
        if style_value.lower().startswith("heading"):
            current_section = content
        section = current_section or f"Paragraph {len(blocks) + 1}"
        blocks.append({"content": content, "section": section, "page_no": None})
    return blocks


def _parse_image(
    file_bytes: bytes,
    normalized_name: str,
    mime_type: str | None,
    chunk_size: int,
    chunk_overlap: int,
) -> ParsedDocument:
    """调用 VisionTextProvider 解析图片，将结果渲染为 Markdown。"""
    provider = get_vision_text_provider()
    result = provider.extract_text(file_bytes)

    blocks = []
    if result.caption:
        blocks.append({"content": f"## Image Description\n\n{result.caption}", "section": "Image Description", "page_no": None})
    if result.ocr_text:
        blocks.append({"content": f"## OCR Text\n\n{result.ocr_text}", "section": "OCR Text", "page_no": None})
    if result.structured_summary:
        blocks.append({"content": f"## Structured Summary\n\n{result.structured_summary}", "section": "Structured Summary", "page_no": None})
    if not blocks:
        raise DocumentParseError("PARSE_EMPTY_CONTENT", "Image parsing returned no content.")

    chunks = _blocks_to_chunks(
        blocks,
        parser_name="vision_text",
        source_extension="",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        metadata_extra={
            "sourceModality": "image",
            "region": "full",
            "visionConfidence": "unknown",
        },
    )
    return ParsedDocument(
        parser_name="vision_text",
        parser_version=PARSER_VERSION,
        source_file_name=normalized_name,
        mime_type=mime_type,
        chunks=chunks,
    )


def _normalize_text(text: str) -> str:
    """统一换行与空白，避免同一内容因平台换行产生不同 hash。"""
    normalized = re.sub(r"\r\n?", "\n", text)
    normalized = re.sub(r"[\t ]+", " ", normalized)
    return normalized.strip()


def _paragraphs(text: str) -> list[str]:
    """按空行切段；没有空行时保留整段文本。"""
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def _blocks_to_chunks(
    blocks: list[dict],
    parser_name: str,
    source_extension: str,
    chunk_size: int,
    chunk_overlap: int,
    metadata_extra: dict | None = None,
) -> list[ParsedChunk]:
    """把解析 block 切成固定上限 Chunk，并保留页码、章节和解析器 metadata。"""
    chunks: list[ParsedChunk] = []
    overlap = max(0, min(chunk_overlap, chunk_size // 2))
    for block_index, block in enumerate(blocks, start=1):
        content = str(block["content"]).strip()
        if not content:
            continue
        start = 0
        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunk_content = content[start:end].strip()
            if chunk_content:
                metadata = {
                    "parserName": parser_name,
                    "parserVersion": PARSER_VERSION,
                    "sourceExtension": source_extension,
                    "blockIndex": block_index,
                    "charStart": start,
                    "charEnd": end,
                }
                if metadata_extra:
                    metadata.update(metadata_extra)
                chunks.append(
                    ParsedChunk(
                        content=chunk_content,
                        token_count=_estimate_token_count(chunk_content),
                        section=block.get("section"),
                        page_no=block.get("page_no"),
                        metadata=metadata,
                    )
                )
            if end >= len(content):
                break
            start = max(end - overlap, start + 1)
    return chunks


def _estimate_token_count(content: str) -> int:
    """使用轻量估算记录 token 数，真实 tokenizer 可在后续按模型替换。"""
    ascii_chars = sum(1 for char in content if ord(char) < 128)
    non_ascii_chars = len(content) - ascii_chars
    return max(1, ascii_chars // 4 + non_ascii_chars)
