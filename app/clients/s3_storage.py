import logging
from io import BytesIO

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class S3StorageClient:
    """S3-compatible storage client (works with MinIO and AWS S3)."""

    def __init__(
        self, endpoint_url: str, bucket: str, access_key: str, secret_key: str
    ):
        self._bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._s3.head_bucket(Bucket=self._bucket)
        except self._s3.exceptions.ClientError:
            self._s3.create_bucket(Bucket=self._bucket)
            logger.info("Created S3 bucket: %s", self._bucket)

    async def get_upload_url(self, path: str, content_type: str) -> str:
        return path

    async def upload_file(
        self, upload_url: str, data: bytes, content_type: str
    ) -> None:
        self._s3.upload_fileobj(
            BytesIO(data),
            self._bucket,
            upload_url,
            ExtraArgs={"ContentType": content_type},
        )
        logger.info("Uploaded to S3: %s (%d bytes)", upload_url, len(data))

    async def read_file(self, path: str) -> bytes:
        response = self._s3.get_object(Bucket=self._bucket, Key=path)
        return response["Body"].read()

    async def download_file(self, path: str, local_path: str) -> None:
        self._s3.download_file(self._bucket, path, local_path)
