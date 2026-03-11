from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from pitchcopytrade.storage.minio import MinioStorage, StorageObject


@dataclass
class FakePutResult:
    etag: str = "etag-1"
    version_id: str | None = "v1"


@dataclass
class FakeStatResult:
    size: int
    content_type: str
    etag: str = "etag-stat"
    version_id: str | None = "v-stat"


class FakeDownloadResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.closed = False
        self.released = False

    def read(self) -> bytes:
        return self._data

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True


class FakeDeleteError:
    def __init__(self, object_name: str) -> None:
        self.object_name = object_name


class FakeMinioClient:
    def __init__(self) -> None:
        self.bucket_exists_value = False
        self.created_buckets: list[str] = []
        self.put_calls: list[tuple[str, str, int, str]] = []
        self.objects: dict[str, bytes] = {}
        self.removed: list[str] = []

    def bucket_exists(self, bucket_name: str) -> bool:
        return self.bucket_exists_value

    def make_bucket(self, bucket_name: str) -> None:
        self.created_buckets.append(bucket_name)
        self.bucket_exists_value = True

    def put_object(self, bucket_name: str, object_key: str, data, length: int, content_type: str) -> FakePutResult:
        payload = data.read()
        self.put_calls.append((bucket_name, object_key, length, content_type))
        self.objects[object_key] = payload
        return FakePutResult()

    def get_object(self, bucket_name: str, object_key: str) -> FakeDownloadResponse:
        return FakeDownloadResponse(self.objects[object_key])

    def remove_object(self, bucket_name: str, object_key: str) -> None:
        self.removed.append(object_key)
        self.objects.pop(object_key, None)

    def remove_objects(self, bucket_name: str, delete_objects):
        collected = list(delete_objects)
        names = [getattr(item, "object_name", getattr(item, "name", None)) for item in collected]
        self.removed.extend(name for name in names if name is not None)
        return [FakeDeleteError(names[-1])] if names else []

    def stat_object(self, bucket_name: str, object_key: str) -> FakeStatResult:
        return FakeStatResult(size=len(self.objects[object_key]), content_type="application/pdf")


def test_bootstrap_creates_bucket_when_missing() -> None:
    client = FakeMinioClient()
    storage = MinioStorage(client=client, bucket_name="uploads")

    storage.bootstrap()

    assert client.created_buckets == ["uploads"]


def test_upload_and_stat_object_metadata() -> None:
    client = FakeMinioClient()
    storage = MinioStorage(client=client, bucket_name="uploads")

    uploaded = storage.upload_bytes("signals/test.pdf", b"payload", "application/pdf")
    stat = storage.stat_object("signals/test.pdf")

    assert isinstance(uploaded, StorageObject)
    assert uploaded.bucket_name == "uploads"
    assert uploaded.object_key == "signals/test.pdf"
    assert uploaded.size_bytes == 7
    assert stat.content_type == "application/pdf"
    assert stat.size_bytes == 7


def test_upload_fileobj_and_download_bytes() -> None:
    client = FakeMinioClient()
    storage = MinioStorage(client=client, bucket_name="uploads")

    uploaded = storage.upload_fileobj("signals/image.png", BytesIO(b"image-data"), 10, "image/png")
    downloaded = storage.download_bytes("signals/image.png")

    assert uploaded.content_type == "image/png"
    assert downloaded == b"image-data"


def test_delete_object_and_delete_many() -> None:
    client = FakeMinioClient()
    storage = MinioStorage(client=client, bucket_name="uploads")
    storage.upload_bytes("a.pdf", b"a", "application/pdf")
    storage.upload_bytes("b.pdf", b"b", "application/pdf")

    storage.delete_object("a.pdf")
    errors = storage.delete_many(["b.pdf", "missing.pdf"])

    assert "a.pdf" in client.removed
    assert "b.pdf" in client.removed
    assert errors == ["missing.pdf"]
