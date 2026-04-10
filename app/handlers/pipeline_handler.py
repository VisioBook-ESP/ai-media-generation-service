import base64
import logging

from app import storage_paths
from app.workflows import animation, flux_location, flux_portrait, scene

logger = logging.getLogger(__name__)


class PipelineHandler:
    def __init__(self, comfyui, publisher, storage, settings):
        self._comfyui = comfyui
        self._publisher = publisher
        self._storage = storage
        self._settings = settings

    async def handle(self, data: dict) -> None:
        user_id = data["userId"]
        project_id = data["projectId"]
        execution_id = data.get("executionId")
        characters = data.get("characters", [])
        locations = data.get("locations", [])
        scenes = data.get("scenes", [])

        await self._publish_progress(execution_id, "pipeline", 0, "Pipeline started")

        # --- Phase 1: generate character references ---
        char_ref_paths: dict[str, str] = {}
        await self._publish_progress(execution_id, "reference_generation", 5,
                                     f"Generating {len(characters)} character reference(s)")

        for char in characters:
            name = char["name"]
            try:
                workflow = flux_portrait.build(
                    portrait_prompt=char["portraitPrompt"],
                    negative_prompt=char.get("portraitNegativePrompt", ""),
                    character_id=name,
                )
                image_bytes = await self._comfyui.run_workflow(workflow)

                path = storage_paths.character_ref(user_id, project_id, name)
                upload_url = await self._storage.get_upload_url(path, "image/png")
                await self._storage.upload_file(upload_url, image_bytes, "image/png")
                char_ref_paths[name] = path

                await self._publisher.publish("visiobook.ai.reference.completed", {
                    "executionId": execution_id,
                    "projectId": project_id,
                    "characterName": name,
                    "referenceImageUrl": path,
                })
                logger.info("Character reference completed", extra={"character": name})
            except Exception as exc:
                logger.exception("Character reference failed", extra={"character": name})
                await self._publisher.publish("visiobook.ai.reference.failed", {
                    "executionId": execution_id,
                    "projectId": project_id,
                    "characterName": name,
                    "error": str(exc),
                })

        # --- Phase 2: generate location references ---
        loc_ref_paths: dict[str, str] = {}
        await self._publish_progress(execution_id, "reference_generation", 10,
                                     f"Generating {len(locations)} location reference(s)")

        for loc in locations:
            location_id = loc["locationId"]
            try:
                workflow = flux_location.build(
                    location_prompt=loc["descriptionPrompt"],
                    negative_prompt=loc.get("negativePrompt", ""),
                    location_id=location_id,
                )
                image_bytes = await self._comfyui.run_workflow(workflow)

                path = storage_paths.location_ref(user_id, project_id, location_id)
                upload_url = await self._storage.get_upload_url(path, "image/png")
                await self._storage.upload_file(upload_url, image_bytes, "image/png")
                loc_ref_paths[location_id] = path

                await self._publisher.publish("visiobook.ai.reference.completed", {
                    "executionId": execution_id,
                    "projectId": project_id,
                    "locationId": location_id,
                    "referenceImageUrl": path,
                })
                logger.info("Location reference completed", extra={"location_id": location_id})
            except Exception as exc:
                logger.exception("Location reference failed", extra={"location_id": location_id})
                await self._publisher.publish("visiobook.ai.reference.failed", {
                    "executionId": execution_id,
                    "projectId": project_id,
                    "locationId": location_id,
                    "error": str(exc),
                })

        # --- Phase 3: generate scene images ---
        sorted_scenes = sorted(scenes, key=lambda s: s.get("order", 0))
        total_scenes = len(sorted_scenes)
        scene_image_paths: dict[int, str] = {}

        await self._publish_progress(execution_id, "image_generation", 15,
                                     f"Generating {total_scenes} scene image(s)")

        for i, scene_data in enumerate(sorted_scenes):
            order = scene_data["order"]
            scene_id = f"scene_{order}"
            try:
                # Resolve character reference (first character present)
                chars_present = scene_data.get("charactersPresent", [])
                char_ref_url = None
                if chars_present:
                    char_ref_url = char_ref_paths.get(chars_present[0])

                # Resolve location reference
                loc_id = scene_data.get("locationId")
                loc_ref_url = loc_ref_paths.get(loc_id) if loc_id else None

                workflow, images, mode = await scene.build(
                    scene_prompt=scene_data["imagePrompt"],
                    visual_style="",
                    negative_prompt=scene_data.get("negativePrompt", ""),
                    character_ref_url=char_ref_url,
                    location_ref_url=loc_ref_url,
                    load_image_b64=self._load_image_b64,
                    scene_id=scene_id,
                )

                image_bytes = await self._comfyui.run_workflow(workflow, images=images)

                path = storage_paths.scene_image(user_id, project_id, scene_id)
                upload_url = await self._storage.get_upload_url(path, "image/png")
                await self._storage.upload_file(upload_url, image_bytes, "image/png")
                scene_image_paths[order] = path

                await self._publisher.publish("visiobook.ai.media.image.completed", {
                    "executionId": execution_id,
                    "sceneOrder": order,
                    "mediaUrl": path,
                    "mode": mode,
                })
                logger.info("Scene image completed", extra={"scene_id": scene_id, "mode": mode})
            except Exception as exc:
                logger.exception("Scene image failed", extra={"scene_id": scene_id})
                await self._publisher.publish("visiobook.ai.media.failed", {
                    "executionId": execution_id,
                    "sceneOrder": order,
                    "error": str(exc),
                })

            progress = 15 + int((i + 1) / total_scenes * 25)
            await self._publish_progress(execution_id, "image_generation", progress,
                                         f"Scene {i + 1}/{total_scenes} done")

        # --- Phase 4: generate animations ---
        await self._publish_progress(execution_id, "animation_generation", 45,
                                     f"Animating {len(scene_image_paths)} scene(s)")

        for i, (order, image_path) in enumerate(sorted(scene_image_paths.items())):
            scene_id = f"scene_{order}"
            scene_data = sorted_scenes[i] if i < len(sorted_scenes) else {}
            try:
                image_b64 = await self._load_image_b64(image_path)

                workflow, anim_images = animation.build(
                    scene_prompt=scene_data.get("imagePrompt", ""),
                    scene_id=scene_id,
                )
                anim_images[0]["image"] = image_b64

                video_bytes = await self._comfyui.run_workflow(
                    workflow, images=anim_images, output_type="video"
                )

                path = storage_paths.animated_scene(user_id, project_id, scene_id)
                upload_url = await self._storage.get_upload_url(path, "image/webp")
                await self._storage.upload_file(upload_url, video_bytes, "image/webp")

                await self._publisher.publish("visiobook.ai.media.animation.completed", {
                    "executionId": execution_id,
                    "sceneOrder": order,
                    "mediaUrl": path,
                })
                logger.info("Scene animation completed", extra={"scene_id": scene_id})
            except Exception as exc:
                logger.exception("Scene animation failed", extra={"scene_id": scene_id})
                await self._publisher.publish("visiobook.ai.media.failed", {
                    "executionId": execution_id,
                    "sceneOrder": order,
                    "error": str(exc),
                })

            progress = 45 + int((i + 1) / len(scene_image_paths) * 50)
            await self._publish_progress(execution_id, "animation_generation", progress,
                                         f"Animation {i + 1}/{len(scene_image_paths)} done")

        await self._publish_progress(execution_id, "pipeline", 100, "Pipeline completed")
        await self._publisher.publish("visiobook.ai.pipeline.completed", {
            "executionId": execution_id,
            "projectId": project_id,
        })

    async def _load_image_b64(self, storage_path: str) -> str:
        data = await self._storage.read_file(storage_path)
        return base64.b64encode(data).decode("utf-8")

    async def _publish_progress(self, execution_id, step, progress, message):
        await self._publisher.publish("visiobook.ai.progress", {
            "executionId": execution_id,
            "step": step,
            "progress": progress,
            "message": message,
        })
