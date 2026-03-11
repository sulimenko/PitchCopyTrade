from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from pitchcopytrade.storage.base import StorageObject
from pitchcopytrade.storage.local import LocalFilesystemStorage


def test_bootstrap_creates_blob_root(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage" / "blob")

    storage.bootstrap()

    assert (tmp_path / "storage" / "blob").is_dir()


def test_upload_and_stat_object_metadata(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage" / "blob")

    uploaded = storage.upload_bytes("signals/test.pdf", b"payload", "application/pdf")
    stat = storage.stat_object("signals/test.pdf")

    assert isinstance(uploaded, StorageObject)
    assert uploaded.bucket_name == "blob"
    assert uploaded.object_key == "signals/test.pdf"
    assert uploaded.size_bytes == 7
    assert uploaded.local_path is not None
    assert stat.content_type == "application/pdf"
    assert stat.size_bytes == 7


def test_upload_fileobj_and_download_bytes(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage" / "blob")

    uploaded = storage.upload_fileobj("signals/image.png", BytesIO(b"image-data"), 10, "image/png")
    downloaded = storage.download_bytes("signals/image.png")

    assert uploaded.content_type == "image/png"
    assert downloaded == b"image-data"


def test_delete_object_and_delete_many(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage" / "blob")
    storage.upload_bytes("a.pdf", b"a", "application/pdf")
    storage.upload_bytes("nested/b.pdf", b"b", "application/pdf")

    storage.delete_object("a.pdf")
    errors = storage.delete_many(["nested/b.pdf", "missing.pdf"])

    assert not (tmp_path / "storage" / "blob" / "a.pdf").exists()
    assert not (tmp_path / "storage" / "blob" / "nested" / "b.pdf").exists()
    assert errors == []


@pytest.mark.parametrize("object_key", ["../escape.pdf", "/absolute.pdf", ""])
def test_rejects_invalid_object_keys(tmp_path: Path, object_key: str) -> None:
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage" / "blob")

    with pytest.raises(ValueError):
        storage.upload_bytes(object_key, b"payload", "application/pdf")
