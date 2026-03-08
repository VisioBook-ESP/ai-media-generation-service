import base64
import logging

logger = logging.getLogger(__name__)


class WebhookHandler:
    def __init__(self, storage, publisher):
        self._storage = storage
        self._publisher = publisher

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
        images = output.get("images", [])
        if not images:
            raise ValueError("RunPod output contains no images")
        image_data = images[0]
        upload_url = await self._storage.get_upload_url(storage_path, "image/png")
        if image_data.get("type") == "base64":
            raw_bytes = base64.b64decode(image_data["data"])
        else:
            raise ValueError(f"Unsupported image format: {image_data.get('type')}")
        await self._storage.upload_file(upload_url, raw_bytes, "image/png")
        return storage_path
