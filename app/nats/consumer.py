import asyncio
import json
import logging
import nats

logger = logging.getLogger(__name__)


async def _run_with_heartbeat(msg, coro):
    """Run a handler coroutine while sending NATS in_progress() heartbeats to prevent redelivery."""
    task = asyncio.create_task(coro)
    try:
        while not task.done():
            await msg.in_progress()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=15)
                return task.result()
            except asyncio.TimeoutError:
                continue
    except Exception:
        if not task.done():
            task.cancel()
        raise
    return task.result()


class NATSConsumer:
    def __init__(self, settings, pipeline_handler):
        self._settings = settings
        self._pipeline_handler = pipeline_handler
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
            "visiobook.media.generate",
            cb=self._on_generate,
            durable="ai-media-gen-pipeline",
            stream=self._settings.NATS_STREAM,
        )
        logger.info("NATS consumer started — listening on visiobook.media.generate")

    async def _on_generate(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            logger.info("Received pipeline event", extra={
                "projectId": data.get("projectId"),
                "executionId": data.get("executionId"),
            })
            await _run_with_heartbeat(msg, self._pipeline_handler.handle(data))
            await msg.ack()
        except Exception as exc:
            logger.exception("Error processing pipeline event", exc_info=exc)
            await msg.nak(delay=5)

    async def stop(self) -> None:
        if self._nc:
            try:
                await self._nc.drain()
            except Exception:
                pass
            logger.info("NATS consumer stopped")
