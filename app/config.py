from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PORT: int = 8087
    ENV: str = "development"

    # NATS JetStream
    NATS_URL: str = "nats://nats:4222"
    NATS_STREAM: str = "visiobook"

    # ComfyUI (RunPod pod)
    COMFYUI_URL: str = "http://localhost:8188"

    # MinIO storage
    MINIO_ENDPOINT: str = "localhost"
    MINIO_PORT: str = "9000"
    MINIO_USE_SSL: str = "false"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_RESULTS: str = "analysis-results"

    @property
    def S3_ENDPOINT_URL(self) -> str:
        scheme = "https" if self.MINIO_USE_SSL.lower() == "true" else "http"
        return f"{scheme}://{self.MINIO_ENDPOINT}:{self.MINIO_PORT}"
