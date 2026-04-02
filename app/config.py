from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PORT: int = 8087
    ENV: str = "development"
    LOG_LEVEL: str = "info"

    NATS_URL: str = "nats://nats:4222"
    NATS_STREAM: str = "visiobook"

    STORAGE_URL: str = "http://storage-service:8085"

    COMFYUI_URL: str = "http://localhost:8188"

    DEFAULT_IMAGE_WIDTH: int = 1024
    DEFAULT_IMAGE_HEIGHT: int = 1024

    class Config:
        env_file = ".env"
