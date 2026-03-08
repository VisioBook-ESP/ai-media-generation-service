import json
import logging
import nats

logger = logging.getLogger(__name__)


class NATSPublisher:
    def __init__(self, settings):
        self._nats_url = settings.NATS_URL
        self._nc = None
        self._js = None

    async def connect(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        self._js = self._nc.jetstream()
        logger.info("NATS publisher connected")

    async def publish(self, subject: str, payload: dict) -> None:
        if self._js is None:
            raise RuntimeError("Publisher not connected — call connect() first")
        await self._js.publish(subject, json.dumps(payload).encode())

    async def disconnect(self) -> None:
        if self._nc:
            await self._nc.drain()
            logger.info("NATS publisher disconnected")
