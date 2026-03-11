from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.helpers import ObjectWriteResult

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.storage.base import StorageObject


class MinioStorage:
    provider_name = "minio"

    def __init__(self, client: Minio | None = None, bucket_name: str | None = None) -> None:
        settings = get_settings()
        self.bucket_name = bucket_name or settings.minio.bucket_uploads
        self.client = client or Minio(
            settings.minio.endpoint,
            access_key=settings.minio.root_user,
            secret_key=settings.minio.root_password.get_secret_value(),
            secure=settings.minio.secure,
        )

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def bootstrap(self) -> None:
        self.ensure_bucket()

    def upload_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> StorageObject:
        stream = BytesIO(data)
        result = self.client.put_object(
            self.bucket_name,
            object_key,
            stream,
            length=len(data),
            content_type=content_type,
        )
        return self._to_storage_object(result, object_key=object_key, content_type=content_type, size_bytes=len(data))

    def upload_fileobj(
        self,
        object_key: str,
        fileobj: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StorageObject:
        result = self.client.put_object(
            self.bucket_name,
            object_key,
            fileobj,
            length=size_bytes,
            content_type=content_type,
        )
        return self._to_storage_object(result, object_key=object_key, content_type=content_type, size_bytes=size_bytes)

    def download_bytes(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket_name, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_object(self, object_key: str) -> None:
        self.client.remove_object(self.bucket_name, object_key)

    def delete_many(self, object_keys: list[str]) -> list[str]:
        errors = self.client.remove_objects(
            self.bucket_name,
            [DeleteObject(object_key) for object_key in object_keys],
        )
        return [error.object_name for error in errors]

    def stat_object(self, object_key: str) -> StorageObject:
        stat = self.client.stat_object(self.bucket_name, object_key)
        return StorageObject(
            bucket_name=self.bucket_name,
            object_key=object_key,
            content_type=stat.content_type or "application/octet-stream",
            size_bytes=stat.size,
            etag=getattr(stat, "etag", None),
            version_id=getattr(stat, "version_id", None),
        )

    def _to_storage_object(
        self,
        result: ObjectWriteResult,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
    ) -> StorageObject:
        return StorageObject(
            bucket_name=self.bucket_name,
            object_key=object_key,
            content_type=content_type,
            size_bytes=size_bytes,
            etag=getattr(result, "etag", None),
            version_id=getattr(result, "version_id", None),
        )
