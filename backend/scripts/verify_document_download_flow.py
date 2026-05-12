"""验证文档原文下载流程的源码级契约。

本脚本聚焦下载入口、对象存储缺失提示和前端列表操作，
避免依赖真实 MinIO 常驻服务即可覆盖本次最小闭环。
"""

from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    """按 UTF-8 读取仓库文件，避免中文提示在 Windows 环境乱码。"""
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """校验关键实现片段存在，用明确错误说明指出缺失项。"""
    if needle not in source:
        raise AssertionError(message)


def verify_backend_download_contract() -> None:
    """校验后端暴露原文下载接口，并从对象存储读取 active version 文件。"""
    service = _read("backend/app/services/document_service.py")
    routes = _read("backend/app/api/routes/documents.py")
    storage = _read("backend/app/services/object_storage.py")

    _assert_contains(service, "class DocumentSourceFileUnavailableError", "缺少原文件不可用业务异常")
    _assert_contains(service, "def download_document_source(", "服务层缺少原文下载函数")
    _assert_contains(service, '"kb.document.download"', "下载服务缺少 kb.document.download 权限校验")
    _assert_contains(service, 'document_row["active_version_id"]', "下载服务未基于 active version 读取原文件")
    _assert_contains(service, "storage.get_object", "下载服务未从对象存储读取原始文件")
    _assert_contains(service, "原始文件在对象存储中不存在", "缺少对象存储文件缺失的友好提示")
    _assert_contains(storage, 'code", "") in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}', "MinIO 缺失对象未转换为空结果")
    _assert_contains(routes, '@router.get("/{document_id}/download")', "Documents 路由缺少下载接口")
    _assert_contains(routes, "Content-Disposition", "下载接口缺少文件名响应头")
    _assert_contains(routes, "DocumentSourceFileUnavailableError", "API 层未捕获原文件不可用异常")


def verify_frontend_download_contract() -> None:
    """校验 P06 文档列表提供单文档下载入口和友好失败反馈。"""
    api_client = _read("frontend/src/app/services/apiClient.ts")
    service = _read("frontend/src/app/services/documentService.ts")
    page = _read("frontend/src/app/pages/P06_DocumentCenter.tsx")

    _assert_contains(api_client, "apiDownload", "前端 API 客户端缺少二进制下载方法")
    _assert_contains(service, "downloadDocumentSource", "前端文档服务缺少下载函数")
    _assert_contains(service, "/download", "前端下载函数未调用后端下载路径")
    _assert_contains(page, "handleDownloadDocument", "P06 缺少下载处理函数")
    _assert_contains(page, "原文下载", "P06 缺少原文下载按钮文案或提示")
    _assert_contains(page, "原文档暂不可下载", "P06 缺少下载失败友好提示")


def main() -> None:
    """执行文档原文下载源码级验收。"""
    verify_backend_download_contract()
    verify_frontend_download_contract()
    print("Document download flow verification passed.")


if __name__ == "__main__":
    main()
