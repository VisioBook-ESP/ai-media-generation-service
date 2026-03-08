import json
import logging
import nats

logger = logging.getLogger(__name__)


class NATSConsumer:
    def __init__(self, settings, reference_handler):
        self._settings = settings
        self._reference_handler = reference_handler
        self._nc = None

    async def start(self) -> None:
        self._nc = await nats.connect(self._settings.NATS_URL)
        js = self._nc.jetstream()

        try:
            await js.stream_info(self._settings.NATS_STREAM)
            logger.info("NATS stream '%s' already exists", self._settings.NATS_STREAM)
        except nats.js.errors.NotFoundError:
            await js.add_stream(name=self._settings.NATS_STREAM, subjects=["visiobook.>"])
            logger.info("NATS stream '%s' created", self._settings.NATS_STREAM)

        await js.subscribe(
            "visiobook.media.generate_references",
            cb=self._on_generate_references,
            durable="ai-media-gen-refs",
            stream=self._settings.NATS_STREAM,
        )
        logger.info("NATS consumer started — listening on visiobook.media.generate_references")

    async def _on_generate_references(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            logger.info("Received generate_references event", extra={"projectId": data.get("projectId")})
            await self._reference_handler.handle(data)
            await msg.ack()
        except Exception as exc:
            logger.exception("Error processing generate_references", exc_info=exc)
            await msg.nak(delay=5)

    async def stop(self) -> None:
        if self._nc:
            await self._nc.drain()
            logger.info("NATS consumer stopped")
