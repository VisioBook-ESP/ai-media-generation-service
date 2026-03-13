import base64
import logging

from app.workflows import wan_video

logger = logging.getLogger(__name__)


class WebhookHandler:
    def __init__(self, storage, publisher, runpod=None, settings=None):
        self._storage = storage
        self._publisher = publisher
        self._runpod = runpod
        self._settings = settings

    async def handle(self, body: dict) -> None:
        status = body.get("status")
        metadata = (body.get("input") or {}).get("metadata", {})
        job_type = metadata.get("job_type")
        job_id = body.get("id")

        logger.info("RunPod webhook received", extra={"job_id": job_id, "job_type": job_type, "status": status})

        if status == "COMPLETED":
            output = body.get("output", {})
            if job_type == "character_reference":
                await self._handle_character_reference(metadata, output)
            elif job_type == "location_reference":
                await self._handle_location_reference(metadata, output)
            elif job_type == "scene_image":
                await self._handle_scene_image(metadata, output)
            elif job_type == "scene_video":
                await self._handle_scene_video(metadata, output)
            else:
                logger.warning("Unknown job_type in webhook", extra={"job_type": job_type})
        elif status == "FAILED":
            await self._handle_failure(metadata, body.get("error"))
        else:
            logger.debug("Ignoring webhook status", extra={"status": status})

    async def _handle_character_reference(self, metadata: dict, output: dict) -> None:
        character_id = metadata["character_id"]
        project_id = metadata["project_id"]
        storage_path = f"projects/{project_id}/characters/{character_id}/reference.png"
        image_url = await self._upload_image(output, storage_path)
        await self._publisher.publish("visiobook.ai.reference.completed", {
            "projectId": project_id,
            "characterId": character_id,
            "referenceImageUrl": image_url,
        })
        logger.info("Character reference completed", extra={"character_id": character_id})

    async def _handle_location_reference(self, metadata: dict, output: dict) -> None:
        location_id = metadata["location_id"]
        project_id = metadata["project_id"]
        storage_path = f"projects/{project_id}/locations/{location_id}/reference.png"
        image_url = await self._upload_image(output, storage_path)
        await self._publisher.publish("visiobook.ai.reference.completed", {
            "projectId": project_id,
            "locationId": location_id,
            "referenceImageUrl": image_url,
        })
        logger.info("Location reference completed", extra={"location_id": location_id})

    async def _handle_scene_image(self, metadata: dict, output: dict) -> None:
        scene_id = metadata["scene_id"]
        project_id = metadata["project_id"]
        execution_id = metadata.get("execution_id")
        video_prompt = metadata.get("video_prompt", "")

        storage_path = f"projects/{project_id}/scenes/{scene_id}/image.png"
        raw_bytes = await self._extract_image_bytes(output)
        upload_url = await self._storage.get_upload_url(storage_path, "image/png")
        await self._storage.upload_file(upload_url, raw_bytes, "image/png")

        await self._publisher.publish("visiobook.ai.media.image.completed", {
            "executionId": execution_id,
            "sceneId": scene_id,
            "mediaUrl": storage_path,
        })
        logger.info("Scene image completed", extra={"scene_id": scene_id})

        # Launch video generation
        if self._runpod and self._settings and self._settings.RUNPOD_ENDPOINT_VIDEO:
            image_b64 = base64.b64encode(raw_bytes).decode("utf-8")
            workflow = wan_video.build(
                video_prompt=video_prompt,
                image_name="scene_image.png",
                width=self._settings.DEFAULT_VIDEO_WIDTH,
                height=self._settings.DEFAULT_VIDEO_HEIGHT,
                length=self._settings.DEFAULT_VIDEO_LENGTH,
            )
            job_id = await self._runpod.submit_job(
                endpoint_id=self._settings.RUNPOD_ENDPOINT_VIDEO,
                workflow=workflow,
                images=[{"name": "scene_image.png", "image": image_b64}],
                metadata={
                    "job_type": "scene_video",
                    "scene_id": scene_id,
                    "project_id": project_id,
                    "execution_id": execution_id,
                },
            )
            logger.info("Scene video job submitted", extra={"job_id": job_id, "scene_id": scene_id})
        else:
            logger.debug("No video endpoint configured — skipping video generation")

    async def _handle_scene_video(self, metadata: dict, output: dict) -> None:
        scene_id = metadata["scene_id"]
        project_id = metadata["project_id"]
        execution_id = metadata.get("execution_id")

        storage_path = f"projects/{project_id}/scenes/{scene_id}/video.webp"
        images = output.get("images", [])
        if not images:
            raise ValueError("RunPod video output contains no images")
        image_data = images[0]
        if image_data.get("type") == "base64":
            raw_bytes = base64.b64decode(image_data["data"])
        else:
            raise ValueError(f"Unsupported video format: {image_data.get('type')}")

        upload_url = await self._storage.get_upload_url(storage_path, "image/webp")
        await self._storage.upload_file(upload_url, raw_bytes, "image/webp")

        await self._publisher.publish("visiobook.ai.media.video.completed", {
            "executionId": execution_id,
            "sceneId": scene_id,
            "mediaUrl": storage_path,
        })
        logger.info("Scene video completed", extra={"scene_id": scene_id})

    async def _handle_failure(self, metadata: dict, error) -> None:
        payload = {
            "executionId": metadata.get("execution_id"),
            "step": metadata.get("job_type"),
            "error": str(error),
        }
        if "character_id" in metadata:
            payload["characterId"] = metadata["character_id"]
            payload["projectId"] = metadata.get("project_id")
            await self._publisher.publish("visiobook.ai.reference.failed", payload)
        elif "location_id" in metadata:
            payload["locationId"] = metadata["location_id"]
            payload["projectId"] = metadata.get("project_id")
            await self._publisher.publish("visiobook.ai.reference.failed", payload)
        else:
            payload["sceneId"] = metadata.get("scene_id")
            await self._publisher.publish("visiobook.ai.media.failed", payload)
        logger.error("RunPod job failed", extra={"metadata": metadata, "error": str(error)})

    async def _upload_image(self, output: dict, storage_path: str) -> str:
        raw_bytes = await self._extract_image_bytes(output)
        upload_url = await self._storage.get_upload_url(storage_path, "image/png")
        await self._storage.upload_file(upload_url, raw_bytes, "image/png")
        return storage_path

    async def _extract_image_bytes(self, output: dict) -> bytes:
        images = output.get("images", [])
        if not images:
            raise ValueError("RunPod output contains no images")
        image_data = images[0]
        if image_data.get("type") == "base64":
            return base64.b64decode(image_data["data"])
        raise ValueError(f"Unsupported image format: {image_data.get('type')}")
