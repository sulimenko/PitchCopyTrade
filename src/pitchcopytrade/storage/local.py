from __future__ import annotations

import mimetypes
from hashlib import md5
from io import BytesIO
from pathlib import Path, PurePosixPath
from shutil import copytree
from typing import BinaryIO

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.storage.base import StorageObject


class LocalFilesystemStorage:
    provider_name = "local"

    def __init__(
        self,
        root_dir: str | Path | None = None,
        seed_root_dir: str | Path | None = None,
    ) -> None:
        settings = get_settings()
        self.root_dir = Path(root_dir or settings.storage.blob_root)
        self.seed_root_dir = Path(seed_root_dir or settings.storage.seed_blob_root)

    def bootstrap(self) -> None:
        if not self.root_dir.exists() and self.seed_root_dir.exists() and self.seed_root_dir != self.root_dir:
            copytree(self.seed_root_dir, self.root_dir, dirs_exist_ok=True)
            return
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def upload_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> StorageObject:
        target = self._resolve_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return self._build_storage_object(
            object_key=object_key,
            content_type=content_type,
            size_bytes=len(data),
            payload=data,
        )

    def upload_fileobj(
        self,
        object_key: str,
        fileobj: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StorageObject:
        data = fileobj.read()
        target = self._resolve_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return self._build_storage_object(
            object_key=object_key,
            content_type=content_type,
            size_bytes=size_bytes,
            payload=data,
        )

    def download_bytes(self, object_key: str) -> bytes:
        self.bootstrap()
        target = self._resolve_path(object_key)
        return target.read_bytes()

    def delete_object(self, object_key: str) -> None:
        target = self._resolve_path(object_key)
        if target.exists():
            target.unlink()
        self._cleanup_empty_dirs(target.parent)

    def delete_many(self, object_keys: list[str]) -> list[str]:
        errors: list[str] = []
        for object_key in object_keys:
            try:
                self.delete_object(object_key)
            except OSError:
                errors.append(object_key)
        return errors

    def stat_object(self, object_key: str) -> StorageObject:
        self.bootstrap()
        target = self._resolve_path(object_key)
        stat = target.stat()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return StorageObject(
            object_key=self._normalize_object_key(object_key),
            content_type=content_type,
            size_bytes=stat.st_size,
            etag=md5(target.read_bytes(), usedforsecurity=False).hexdigest(),
            local_path=str(target),
        )

    def _build_storage_object(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
        payload: bytes,
    ) -> StorageObject:
        target = self._resolve_path(object_key)
        return StorageObject(
            object_key=self._normalize_object_key(object_key),
            content_type=content_type,
            size_bytes=size_bytes,
            etag=md5(payload, usedforsecurity=False).hexdigest(),
            local_path=str(target),
        )

    def _resolve_path(self, object_key: str) -> Path:
        normalized = self._normalize_object_key(object_key)
        target = self.root_dir.joinpath(*PurePosixPath(normalized).parts)
        target.relative_to(self.root_dir)
        return target

    def _normalize_object_key(self, object_key: str) -> str:
        normalized = PurePosixPath(object_key.strip()).as_posix()
        if not normalized or normalized == ".":
            raise ValueError("object_key must not be empty")
        if normalized.startswith("/"):
            raise ValueError("object_key must be relative")
        parts = PurePosixPath(normalized).parts
        if any(part == ".." for part in parts):
            raise ValueError("object_key must not escape storage root")
        return normalized

    def _cleanup_empty_dirs(self, start: Path) -> None:
        current = start
        while current != self.root_dir and current.exists():
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
