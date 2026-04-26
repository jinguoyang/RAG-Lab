from dataclasses import dataclass
from io import BytesIO

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class StoredObject:
    """对象存储写入结果，供业务表记录可追踪的 bucket 与 object key。"""

    bucket: str
    object_key: str
    size: int


class ObjectStorageError(RuntimeError):
    """对象存储写入或配置异常，API 层会映射为稳定错误码。"""


class ObjectStorageProvider:
    """对象存储 Provider 抽象，避免业务服务直接依赖 MinIO SDK。"""

    def put_object(
        self,
        object_key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        raise NotImplementedError

    def delete_object(self, object_key: str) -> None:
        raise NotImplementedError


class MetadataOnlyStorageProvider(ObjectStorageProvider):
    """开发期占位 Provider，只保留对象引用，便于无 MinIO 环境继续联调。"""

    def __init__(self, bucket: str) -> None:
        self._bucket = bucket

    def put_object(
        self,
        object_key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        return StoredObject(bucket=self._bucket, object_key=object_key, size=len(data))

    def delete_object(self, object_key: str) -> None:
        return None


class MinioStorageProvider(ObjectStorageProvider):
    """MinIO Provider，负责原始上传文件的真实对象写入和失败补偿删除。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.minio_endpoint or not settings.minio_access_key or not settings.minio_secret_key:
            raise ObjectStorageError(
                "MinIO storage requires RAG_LAB_MINIO_ENDPOINT, "
                "RAG_LAB_MINIO_ACCESS_KEY and RAG_LAB_MINIO_SECRET_KEY."
            )

        from minio import Minio

        self._bucket = settings.storage_bucket
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def put_object(
        self,
        object_key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)

            self._client.put_object(
                self._bucket,
                object_key,
                BytesIO(data),
                length=len(data),
                content_type=content_type or "application/octet-stream",
            )
        except Exception as exc:
            raise ObjectStorageError("Object storage write failed.") from exc
        return StoredObject(bucket=self._bucket, object_key=object_key, size=len(data))

    def delete_object(self, object_key: str) -> None:
        self._client.remove_object(self._bucket, object_key)


def get_object_storage_provider() -> ObjectStorageProvider:
    """根据运行配置选择对象存储 Provider，默认不强制本地启动 MinIO。"""
    settings = get_settings()
    if settings.storage_backend == "minio":
        return MinioStorageProvider(settings)
    if settings.storage_backend == "metadata":
        return MetadataOnlyStorageProvider(settings.storage_bucket)
    raise ObjectStorageError(f"Unsupported storage backend: {settings.storage_backend}")
