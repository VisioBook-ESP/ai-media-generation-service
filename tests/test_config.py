from app.config import Settings


class TestS3EndpointUrl:
    def test_http_when_ssl_false(self):
        s = Settings(MINIO_ENDPOINT="minio", MINIO_PORT="9000", MINIO_USE_SSL="false")
        assert s.S3_ENDPOINT_URL == "http://minio:9000"

    def test_https_when_ssl_true(self):
        s = Settings(
            MINIO_ENDPOINT="s3.example", MINIO_PORT="443", MINIO_USE_SSL="true"
        )
        assert s.S3_ENDPOINT_URL == "https://s3.example:443"

    def test_ssl_case_insensitive(self):
        s = Settings(MINIO_USE_SSL="TRUE")
        assert s.S3_ENDPOINT_URL.startswith("https://")
