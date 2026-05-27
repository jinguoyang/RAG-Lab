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


@celery_app.task(name="document_ingest.run", bind=True, max_retries=3, default_retry_delay=5)
def run_document_ingest_task(self, job_id: str) -> dict:
    """按 IngestJob ID 执行文档解析、切块和索引副本写入。"""
    from app.services.document_service import DocumentConflictError, run_ingest_job_by_id

    try:
        return run_ingest_job_by_id(job_id)
    except DocumentConflictError as exc:
        if "not found" in str(exc).lower() and self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


@celery_app.task(name="library_parse.run", bind=True, max_retries=3, default_retry_delay=5)
def run_library_parse_task(self, job_id: str) -> dict:
    """按 LibraryParseJob ID 执行文档库文本提取。"""
    from app.services.library_service import run_library_parse_job_by_id

    return run_library_parse_job_by_id(job_id)
