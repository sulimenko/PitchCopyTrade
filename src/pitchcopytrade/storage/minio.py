from __future__ import annotations

from minio import Minio

from pitchcopytrade.core.config import get_settings


class MinioStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket_name = settings.minio_bucket_uploads
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=settings.minio_secure,
        )

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
