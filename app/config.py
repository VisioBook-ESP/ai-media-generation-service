from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8087
    ENV: str = "development"
    LOG_LEVEL: str = "info"

    # NATS JetStream
    NATS_URL: str = "nats://nats:4222"
    NATS_STREAM: str = "visiobook"

    # ComfyUI (RunPod pod)
    COMFYUI_URL: str = "http://localhost:8188"

    # S3 / MinIO storage
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_BUCKET: str = "visiobook"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_REGION: str = "us-east-1"

    class Config:
        env_file = ".env"
