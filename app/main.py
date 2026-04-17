import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dev import router as dev_router, start_event_listener
from app.api.health import router as health_router
from app.clients.comfyui import ComfyUIClient
from app.clients.local_storage import LocalStorageClient
from app.clients.s3_storage import S3StorageClient
from app.config import Settings
from app.handlers.pipeline_handler import PipelineHandler
from app.nats.consumer import NATSConsumer
from app.nats.publisher import NATSPublisher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()


def _build_storage(settings: Settings):
    if settings.ENV == "development":
        logger.info("Using local filesystem storage (dev mode)")
        return LocalStorageClient()
    logger.info("Using S3 storage: %s/%s", settings.S3_ENDPOINT_URL, settings.MINIO_BUCKET_RESULTS)
    return S3StorageClient(
        endpoint_url=settings.S3_ENDPOINT_URL,
        bucket=settings.MINIO_BUCKET_RESULTS,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ai-media-generation-service (env=%s)...", settings.ENV)

    publisher = NATSPublisher(settings)
    await publisher.connect()

    storage = _build_storage(settings)
    comfyui = ComfyUIClient(settings.COMFYUI_URL)

    pipeline_handler = PipelineHandler(comfyui, publisher, storage, settings)

    consumer = NATSConsumer(settings, pipeline_handler)
    await consumer.start()

    app.state.settings = settings
    app.state.publisher = publisher
    app.state.nats_consumer = consumer
    app.state.comfyui = comfyui

    # Start dev event listener
    await start_event_listener(settings.NATS_URL, settings.NATS_STREAM)

    logger.info("Service ready on port %s", settings.PORT)
    yield

    logger.info("Shutting down...")
    await consumer.stop()
    await publisher.disconnect()


app = FastAPI(
    title="ai-media-generation-service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(dev_router)
