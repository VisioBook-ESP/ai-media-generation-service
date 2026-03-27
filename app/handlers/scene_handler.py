import base64
import logging

from app.workflows import scene

logger = logging.getLogger(__name__)


class SceneHandler:
    def __init__(self, runpod, publisher, storage, settings):
        self._runpod = runpod
        self._publisher = publisher
        self._storage = storage
        self._settings = settings

    async def handle(self, data: dict) -> None:
        project_id = data["projectId"]
        execution_id = data.get("executionId")
        book_style = data["bookStyle"]
        scenes = data.get("scenes", [])

        await self._publisher.publish("visiobook.ai.progress", {
            "executionId": execution_id,
            "step": "image_generation",
            "progress": 15,
            "message": f"Starting scene generation: {len(scenes)} scene(s)",
        })

        for scene in scenes:
            scene_id = scene["sceneId"]
            prompt = scene["prompt"]
            character_ref = scene.get("characterRef")
            location_ref = scene.get("locationRef")
            char_ref_url = character_ref.get("referenceImageUrl") if character_ref else None
            loc_ref_url = location_ref.get("referenceImageUrl") if location_ref else None

            workflow, images, mode = await scene.build(
                scene_prompt=prompt["image"],
                visual_style=book_style["visualStyle"],
                negative_prompt=book_style.get("negativePrompt", ""),
                character_ref_url=char_ref_url,
                location_ref_url=loc_ref_url,
                load_image_b64=self._load_image_b64,
            )

            job_id = await self._runpod.submit_job(
                endpoint_id=self._settings.RUNPOD_ENDPOINT_IMAGE,
                workflow=workflow,
                images=images,
                metadata={
                    "job_type": "scene_image",
                    "scene_id": scene_id,
                    "project_id": project_id,
                    "execution_id": execution_id,
                    "scene_mode": mode,
                },
            )
            logger.info("Scene image job submitted", extra={"job_id": job_id, "scene_id": scene_id})

        await self._publisher.publish("visiobook.ai.progress", {
            "executionId": execution_id,
            "step": "image_generation",
            "progress": 20,
            "message": f"All scene jobs queued: {len(scenes)} scene(s)",
        })

    async def _load_image_b64(self, storage_path: str) -> str:
        data = await self._storage.read_file(storage_path)
        return base64.b64encode(data).decode("utf-8")
