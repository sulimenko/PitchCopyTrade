from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class StorageObject:
    object_key: str
    content_type: str
    size_bytes: int
    etag: str | None = None
    version_id: str | None = None
    local_path: str | None = None


class StorageBackend(Protocol):
    provider_name: str

    def bootstrap(self) -> None: ...

    def upload_bytes(
        self,
        object_key: str,
        data: bytes,
        content_type: str,
    ) -> StorageObject: ...

    def upload_fileobj(
        self,
        object_key: str,
        fileobj: BinaryIO,
        size_bytes: int,
        content_type: str,
    ) -> StorageObject: ...

    def download_bytes(self, object_key: str) -> bytes: ...

    def delete_object(self, object_key: str) -> None: ...

    def delete_many(self, object_keys: list[str]) -> list[str]: ...

    def stat_object(self, object_key: str) -> StorageObject: ...
