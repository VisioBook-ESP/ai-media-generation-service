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
    def __init__(self, settings, reference_handler, scene_handler=None, animation_handler=None):
        self._settings = settings
        self._reference_handler = reference_handler
        self._scene_handler = scene_handler
        self._animation_handler = animation_handler
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

        if self._scene_handler:
            await js.subscribe(
                "visiobook.workflow.step.image_generation",
                cb=self._on_image_generation,
                durable="ai-media-gen-scenes",
                stream=self._settings.NATS_STREAM,
            )
            logger.info("NATS consumer listening on visiobook.workflow.step.image_generation")

        if self._animation_handler:
            await js.subscribe(
                "visiobook.workflow.step.animation_generation",
                cb=self._on_animation_generation,
                durable="ai-media-gen-animations",
                stream=self._settings.NATS_STREAM,
            )
            logger.info("NATS consumer listening on visiobook.workflow.step.animation_generation")

    async def _on_generate_references(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            logger.info("Received generate_references event", extra={"projectId": data.get("projectId")})
            await _run_with_heartbeat(msg, self._reference_handler.handle(data))
            await msg.ack()
        except Exception as exc:
            logger.exception("Error processing generate_references", exc_info=exc)
            await msg.nak(delay=5)

    async def _on_image_generation(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            logger.info("Received image_generation event", extra={"projectId": data.get("projectId")})
            await _run_with_heartbeat(msg, self._scene_handler.handle(data))
            await msg.ack()
        except Exception as exc:
            logger.exception("Error processing image_generation", exc_info=exc)
            await msg.nak(delay=5)

    async def _on_animation_generation(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            logger.info("Received animation_generation event", extra={"projectId": data.get("projectId")})
            await _run_with_heartbeat(msg, self._animation_handler.handle(data))
            await msg.ack()
        except Exception as exc:
            logger.exception("Error processing animation_generation", exc_info=exc)
            await msg.nak(delay=5)

    async def stop(self) -> None:
        if self._nc:
            try:
                await self._nc.drain()
            except Exception:
                pass
            logger.info("NATS consumer stopped")
