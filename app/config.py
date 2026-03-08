from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8087
    ENV: str = "development"
    LOG_LEVEL: str = "info"

    NATS_URL: str = "nats://nats:4222"
    NATS_STREAM: str = "visiobook"

    STORAGE_URL: str = "http://storage-service:8085"

    RUNPOD_API_KEY: str
    RUNPOD_ENDPOINT_IMAGE: str
    RUNPOD_ENDPOINT_VIDEO: str = ""
    RUNPOD_ENDPOINT_AUDIO: str = ""

    WEBHOOK_BASE_URL: str
    WEBHOOK_SECRET: str = ""

    DEFAULT_IMAGE_WIDTH: int = 1024
    DEFAULT_IMAGE_HEIGHT: int = 1024
    DEFAULT_VIDEO_WIDTH: int = 832
    DEFAULT_VIDEO_HEIGHT: int = 480
    DEFAULT_VIDEO_LENGTH: int = 81
    DEFAULT_VIDEO_FPS: int = 16

    class Config:
        env_file = ".env"
