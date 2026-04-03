import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dev import router as dev_router
from app.api.health import router as health_router
from app.clients.comfyui import ComfyUIClient
from app.clients.local_storage import LocalStorageClient
from app.config import Settings
from app.handlers.animation_handler import AnimationHandler
from app.handlers.reference_handler import ReferenceHandler
from app.handlers.scene_handler import SceneHandler
from app.nats.consumer import NATSConsumer
from app.nats.publisher import NATSPublisher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ai-media-generation-service...")

    publisher = NATSPublisher(settings)
    await publisher.connect()

    storage = LocalStorageClient()
    comfyui = ComfyUIClient(settings.COMFYUI_URL)

    ref_handler = ReferenceHandler(comfyui, publisher, storage, settings)
    scene_handler = SceneHandler(comfyui, publisher, storage, settings)
    animation_handler = AnimationHandler(comfyui, publisher, storage, settings)

    consumer = NATSConsumer(settings, ref_handler, scene_handler, animation_handler)
    await consumer.start()

    app.state.settings = settings
    app.state.publisher = publisher

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
