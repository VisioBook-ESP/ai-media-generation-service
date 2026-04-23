import base64
import logging

from app import storage_paths

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

        logger.info(
            "RunPod webhook received",
            extra={"job_id": job_id, "job_type": job_type, "status": status},
        )

        if status == "COMPLETED":
            output = body.get("output", {})
            if job_type == "character_reference":
                await self._handle_character_reference(metadata, output)
            elif job_type == "location_reference":
                await self._handle_location_reference(metadata, output)
            elif job_type == "scene_image":
                await self._handle_scene_image(metadata, output)
            else:
                logger.warning(
                    "Unknown job_type in webhook", extra={"job_type": job_type}
                )
        elif status == "FAILED":
            await self._handle_failure(metadata, body.get("error"))
        else:
            logger.debug("Ignoring webhook status", extra={"status": status})

    async def _handle_character_reference(self, metadata: dict, output: dict) -> None:
        user_id = metadata["user_id"]
        project_id = metadata["project_id"]
        character_id = metadata["character_id"]
        path = storage_paths.character_ref(user_id, project_id, character_id)
        image_url = await self._upload_image(output, path)
        await self._publisher.publish(
            "visiobook.ai.reference.completed",
            {
                "projectId": project_id,
                "characterId": character_id,
                "referenceImageUrl": image_url,
            },
        )
        logger.info(
            "Character reference completed", extra={"character_id": character_id}
        )

    async def _handle_location_reference(self, metadata: dict, output: dict) -> None:
        user_id = metadata["user_id"]
        project_id = metadata["project_id"]
        location_id = metadata["location_id"]
        path = storage_paths.location_ref(user_id, project_id, location_id)
        image_url = await self._upload_image(output, path)
        await self._publisher.publish(
            "visiobook.ai.reference.completed",
            {
                "projectId": project_id,
                "locationId": location_id,
                "referenceImageUrl": image_url,
            },
        )
        logger.info("Location reference completed", extra={"location_id": location_id})

    async def _handle_scene_image(self, metadata: dict, output: dict) -> None:
        user_id = metadata["user_id"]
        project_id = metadata["project_id"]
        scene_id = metadata["scene_id"]
        execution_id = metadata.get("execution_id")

        path = storage_paths.scene_image(user_id, project_id, scene_id)
        raw_bytes = await self._extract_image_bytes(output)
        upload_url = await self._storage.get_upload_url(path, "image/png")
        await self._storage.upload_file(upload_url, raw_bytes, "image/png")

        await self._publisher.publish(
            "visiobook.ai.media.image.completed",
            {
                "executionId": execution_id,
                "sceneId": scene_id,
                "mediaUrl": path,
            },
        )
        logger.info("Scene image completed", extra={"scene_id": scene_id})

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
        logger.error(
            "RunPod job failed", extra={"metadata": metadata, "error": str(error)}
        )

    async def _upload_image(self, output: dict, path: str) -> str:
        raw_bytes = await self._extract_image_bytes(output)
        upload_url = await self._storage.get_upload_url(path, "image/png")
        await self._storage.upload_file(upload_url, raw_bytes, "image/png")
        return path

    async def _extract_image_bytes(self, output: dict) -> bytes:
        images = output.get("images", [])
        if not images:
            raise ValueError("RunPod output contains no images")
        image_data = images[0]
        if image_data.get("type") == "base64":
            return base64.b64decode(image_data["data"])
        raise ValueError(f"Unsupported image format: {image_data.get('type')}")
