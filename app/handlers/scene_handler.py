import base64
import logging

from app.workflows import flux_scene, flux_scene_redux, flux_scene_pulid, flux_scene_pulid_redux, wan_video

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
            prompts = scene["prompts"]
            characters = scene.get("characters", [])

            location_ref = scene.get("locationRef")
            char_ref_url = characters[0]["referenceImageUrl"] if characters else None
            loc_ref_url = location_ref.get("referenceImageUrl") if location_ref else None

            if char_ref_url and loc_ref_url:
                # PuLID (personnage) + Redux (lieu) simultanément
                char_b64 = await self._load_image_b64(char_ref_url)
                loc_b64 = await self._load_image_b64(loc_ref_url)
                workflow = flux_scene_pulid_redux.build(
                    scene_prompt=prompts["image"],
                    visual_style=book_style["visualStyle"],
                    negative_prompt=book_style.get("negativePrompt", ""),
                )
                images = [
                    {"name": "character.png", "image": char_b64},
                    {"name": "location.png", "image": loc_b64},
                ]
            elif char_ref_url:
                # PuLID seul : préserve l'identité faciale du personnage
                workflow = flux_scene_pulid.build(
                    scene_prompt=prompts["image"],
                    visual_style=book_style["visualStyle"],
                    negative_prompt=book_style.get("negativePrompt", ""),
                )
                images = [{"name": "reference.png", "image": await self._load_image_b64(char_ref_url)}]
            elif loc_ref_url:
                # Redux seul : cohérence de style visuel du lieu
                workflow = flux_scene_redux.build(
                    scene_prompt=prompts["image"],
                    visual_style=book_style["visualStyle"],
                    negative_prompt=book_style.get("negativePrompt", ""),
                )
                images = [{"name": "reference.png", "image": await self._load_image_b64(loc_ref_url)}]
            else:
                workflow = flux_scene.build(
                    scene_prompt=prompts["image"],
                    visual_style=book_style["visualStyle"],
                    negative_prompt=book_style.get("negativePrompt", ""),
                )
                images = []

            job_id = await self._runpod.submit_job(
                endpoint_id=self._settings.RUNPOD_ENDPOINT_IMAGE,
                workflow=workflow,
                images=images,
                metadata={
                    "job_type": "scene_image",
                    "scene_id": scene_id,
                    "project_id": project_id,
                    "execution_id": execution_id,
                    "video_prompt": prompts.get("video", ""),
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
