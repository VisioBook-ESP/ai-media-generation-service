import pytest

from app.clients import s3_storage as s3_mod
from app.clients.s3_storage import S3StorageClient


class _FakeS3:
    def __init__(self, bucket_exists: bool = True):
        self.bucket_exists = bucket_exists
        self.uploaded: list = []
        self.created_buckets: list = []
        self.objects: dict[str, bytes] = {}
        self.downloaded: list = []

        class _Exceptions:
            ClientError = Exception

        self.exceptions = _Exceptions()

    def head_bucket(self, Bucket):
        if not self.bucket_exists:
            raise self.exceptions.ClientError("not found")

    def create_bucket(self, Bucket):
        self.created_buckets.append(Bucket)

    def upload_fileobj(self, body, bucket, key, ExtraArgs=None):
        self.uploaded.append(
            (body.read(), bucket, key, (ExtraArgs or {}).get("ContentType"))
        )

    def get_object(self, Bucket, Key):
        class _Body:
            def __init__(self, data):
                self._data = data

            def read(self):
                return self._data

        return {"Body": _Body(self.objects[Key])}

    def download_file(self, bucket, key, local_path):
        self.downloaded.append((bucket, key, local_path))
        from pathlib import Path

        Path(local_path).write_bytes(self.objects[key])


@pytest.fixture
def patch_boto(monkeypatch):
    def configure(*, bucket_exists: bool = True) -> _FakeS3:
        fake = _FakeS3(bucket_exists=bucket_exists)
        monkeypatch.setattr(s3_mod.boto3, "client", lambda *a, **kw: fake)
        return fake

    return configure


class TestEnsureBucket:
    def test_existing_bucket_not_recreated(self, patch_boto):
        fake = patch_boto(bucket_exists=True)
        S3StorageClient("http://minio", "b", "k", "s")
        assert fake.created_buckets == []

    def test_missing_bucket_is_created(self, patch_boto):
        fake = patch_boto(bucket_exists=False)
        S3StorageClient("http://minio", "b", "k", "s")
        assert fake.created_buckets == ["b"]


class TestS3Operations:
    async def test_get_upload_url_returns_path(self, patch_boto):
        patch_boto()
        c = S3StorageClient("http://minio", "b", "k", "s")
        assert await c.get_upload_url("a/b.png", "image/png") == "a/b.png"

    async def test_upload_file(self, patch_boto):
        fake = patch_boto()
        c = S3StorageClient("http://minio", "b", "k", "s")
        await c.upload_file("path/to.png", b"DATA", "image/png")
        assert fake.uploaded == [(b"DATA", "b", "path/to.png", "image/png")]

    async def test_read_file(self, patch_boto):
        fake = patch_boto()
        fake.objects["k.png"] = b"HELLO"
        c = S3StorageClient("http://minio", "b", "k", "s")
        assert await c.read_file("k.png") == b"HELLO"

    async def test_download_file(self, patch_boto, tmp_path):
        fake = patch_boto()
        fake.objects["x.png"] = b"PIX"
        c = S3StorageClient("http://minio", "b", "k", "s")
        local = tmp_path / "out.png"
        await c.download_file("x.png", str(local))
        assert local.read_bytes() == b"PIX"
        assert fake.downloaded == [("b", "x.png", str(local))]
