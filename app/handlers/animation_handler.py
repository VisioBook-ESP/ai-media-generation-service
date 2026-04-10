import base64
import logging

from app.workflows import animation
from app import storage_paths

logger = logging.getLogger(__name__)


class AnimationHandler:
    def __init__(self, comfyui, publisher, storage, settings):
        self._comfyui = comfyui
        self._publisher = publisher
        self._storage = storage
        self._settings = settings

    async def handle(self, data: dict) -> None:
        user_id = data["userId"]
        project_id = data["projectId"]
        execution_id = data.get("executionId")
        scenes = data.get("scenes", [])

        await self._publisher.publish("visiobook.ai.progress", {
            "executionId": execution_id,
            "step": "animation_generation",
            "progress": 25,
            "message": f"Starting animation: {len(scenes)} scene(s)",
        })

        for scene_data in scenes:
            scene_id = scene_data["sceneId"]
            scene_prompt = scene_data.get("prompt", {}).get("image", "")
            scene_image_url = scene_data.get("sceneImageUrl")

            if not scene_image_url:
                logger.warning("No scene image URL for scene %s, skipping", scene_id)
                continue

            try:
                image_b64 = await self._load_image_b64(scene_image_url)

                workflow, images = animation.build(
                    scene_prompt=scene_prompt,
                    scene_id=scene_id,
                )
                images[0]["image"] = image_b64

                video_bytes = await self._comfyui.run_workflow(
                    workflow, images=images, output_type="video"
                )

                path = storage_paths.animated_scene(user_id, project_id, scene_id)
                upload_url = await self._storage.get_upload_url(path, "image/webp")
                await self._storage.upload_file(upload_url, video_bytes, "image/webp")

                await self._publisher.publish("visiobook.ai.media.animation.completed", {
                    "executionId": execution_id,
                    "sceneId": scene_id,
                    "mediaUrl": path,
                })
                logger.info("Scene animation completed", extra={"scene_id": scene_id})
            except Exception as exc:
                logger.exception("Scene animation failed", extra={"scene_id": scene_id})
                await self._publisher.publish("visiobook.ai.media.failed", {
                    "executionId": execution_id,
                    "sceneId": scene_id,
                    "error": str(exc),
                })

        await self._publisher.publish("visiobook.ai.progress", {
            "executionId": execution_id,
            "step": "animation_generation",
            "progress": 40,
            "message": f"All animations done: {len(scenes)} scene(s)",
        })

    async def _load_image_b64(self, storage_path: str) -> str:
        data = await self._storage.read_file(storage_path)
        return base64.b64encode(data).decode("utf-8")
