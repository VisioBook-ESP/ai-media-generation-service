from pathlib import Path

import pytest

from app.clients import local_storage
from app.clients.local_storage import LocalStorageClient


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(local_storage, "_BASE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def client():
    return LocalStorageClient()


class TestGetUploadUrl:
    async def test_returns_path_prefixed_with_base_dir(self, client, storage_dir):
        url = await client.get_upload_url("a/b/file.png", "image/png")
        assert url == str(storage_dir / "a/b/file.png")

    async def test_creates_parent_directories(self, client, storage_dir):
        await client.get_upload_url("nested/deep/dir/file.png", "image/png")
        assert (storage_dir / "nested/deep/dir").is_dir()

    async def test_no_file_created_yet(self, client, storage_dir):
        url = await client.get_upload_url("a/b/file.png", "image/png")
        assert not Path(url).exists()


class TestUploadFile:
    async def test_writes_bytes_to_disk(self, client, storage_dir):
        dest = storage_dir / "out.png"
        await client.upload_file(str(dest), b"\x89PNG\r\n", "image/png")
        assert dest.read_bytes() == b"\x89PNG\r\n"

    async def test_creates_parent_directories_when_missing(self, client, storage_dir):
        dest = storage_dir / "fresh/dir/file.bin"
        await client.upload_file(str(dest), b"data", "application/octet-stream")
        assert dest.read_bytes() == b"data"

    async def test_overwrites_existing_file(self, client, storage_dir):
        dest = storage_dir / "f.bin"
        dest.write_bytes(b"old")
        await client.upload_file(str(dest), b"new", "application/octet-stream")
        assert dest.read_bytes() == b"new"


class TestReadFile:
    async def test_reads_bytes_back(self, client, storage_dir):
        (storage_dir / "x.bin").write_bytes(b"hello")
        assert await client.read_file("x.bin") == b"hello"

    async def test_reads_from_nested_path(self, client, storage_dir):
        (storage_dir / "a/b").mkdir(parents=True)
        (storage_dir / "a/b/y.bin").write_bytes(b"deep")
        assert await client.read_file("a/b/y.bin") == b"deep"

    async def test_missing_file_raises(self, client, storage_dir):
        with pytest.raises(FileNotFoundError):
            await client.read_file("does_not_exist.bin")


class TestDownloadFile:
    async def test_copies_file_to_target(self, client, storage_dir, tmp_path):
        (storage_dir / "src.bin").write_bytes(b"payload")
        dest = tmp_path / "dest.bin"
        await client.download_file("src.bin", str(dest))
        assert dest.read_bytes() == b"payload"

    async def test_missing_source_raises(self, client, storage_dir, tmp_path):
        with pytest.raises(FileNotFoundError):
            await client.download_file("missing.bin", str(tmp_path / "dest.bin"))


class TestRoundTrip:
    async def test_upload_then_read_returns_same_bytes(self, client, storage_dir):
        path = "user1/proj1/characters/luna/reference.png"
        url = await client.get_upload_url(path, "image/png")
        await client.upload_file(url, b"\x89PNG_payload", "image/png")
        assert await client.read_file(path) == b"\x89PNG_payload"
