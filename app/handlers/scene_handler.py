import base64
import logging

from app.workflows import scene

logger = logging.getLogger(__name__)


class SceneHandler:
    def __init__(self, comfyui, publisher, storage, settings):
        self._comfyui = comfyui
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

        for scene_data in scenes:
            scene_id = scene_data["sceneId"]
            prompt = scene_data["prompt"]
            character_ref = scene_data.get("characterRef")
            location_ref = scene_data.get("locationRef")
            char_ref_url = character_ref.get("referenceImageUrl") if character_ref else None
            loc_ref_url = location_ref.get("referenceImageUrl") if location_ref else None

            try:
                workflow, images, mode = await scene.build(
                    scene_prompt=prompt["image"],
                    visual_style=book_style["visualStyle"],
                    negative_prompt=book_style.get("negativePrompt", ""),
                    character_ref_url=char_ref_url,
                    location_ref_url=loc_ref_url,
                    load_image_b64=self._load_image_b64,
                )

                image_bytes = await self._comfyui.run_workflow(workflow, images=images)

                storage_path = f"projects/{project_id}/scenes/{scene_id}/image.png"
                upload_url = await self._storage.get_upload_url(storage_path, "image/png")
                await self._storage.upload_file(upload_url, image_bytes, "image/png")

                await self._publisher.publish("visiobook.ai.media.image.completed", {
                    "executionId": execution_id,
                    "sceneId": scene_id,
                    "mediaUrl": storage_path,
                })
                logger.info("Scene image completed", extra={"scene_id": scene_id, "mode": mode})
            except Exception as exc:
                logger.exception("Scene image failed", extra={"scene_id": scene_id})
                await self._publisher.publish("visiobook.ai.media.failed", {
                    "executionId": execution_id,
                    "sceneId": scene_id,
                    "error": str(exc),
                })

        await self._publisher.publish("visiobook.ai.progress", {
            "executionId": execution_id,
            "step": "image_generation",
            "progress": 20,
            "message": f"All scenes done: {len(scenes)} scene(s)",
        })

    async def _load_image_b64(self, storage_path: str) -> str:
        data = await self._storage.read_file(storage_path)
        return base64.b64encode(data).decode("utf-8")
