from uuid import UUID

from celery import Celery

from app.core.config import get_settings


settings = get_settings()

celery_app = Celery(
    "rag_lab",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    enable_utc=False,
    result_serializer="json",
    task_serializer="json",
    task_track_started=True,
    timezone="Asia/Hong_Kong",
)


@celery_app.task(name="document_ingest.run")
def run_document_ingest_task(job_id: str) -> dict:
    """按 IngestJob ID 执行文档解析、切块和索引副本写入。"""
    from app.services.document_service import run_ingest_job_by_id

    return run_ingest_job_by_id(UUID(job_id))


@celery_app.task(name="library_parse.run")
def run_library_parse_task(job_id: str) -> dict:
    """按 LibraryParseJob ID 执行文档库文本提取。"""
    from app.services.library_service import run_library_parse_job_by_id

    return run_library_parse_job_by_id(UUID(job_id))
