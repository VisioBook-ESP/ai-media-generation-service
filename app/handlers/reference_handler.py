import logging
from app.workflows import flux_portrait, flux_location

logger = logging.getLogger(__name__)


class ReferenceHandler:
    def __init__(self, comfyui, publisher, storage, settings):
        self._comfyui = comfyui
        self._publisher = publisher
        self._storage = storage
        self._settings = settings

    async def handle(self, data: dict) -> None:
        project_id = data["projectId"]
        execution_id = data.get("executionId")
        book_style = data["bookStyle"]
        characters = data.get("characters", [])
        locations = data.get("locations", [])

        await self._publisher.publish("visiobook.ai.progress", {
            "executionId": execution_id,
            "step": "reference_generation",
            "progress": 5,
            "message": f"Starting generation: {len(characters)} character(s), {len(locations)} location(s)",
        })

        for char in characters:
            character_id = char["characterId"]
            try:
                workflow = flux_portrait.build(
                    physical_description=char["physicalDescription"],
                    visual_style=book_style["visualStyle"],
                    negative_prompt=book_style.get("negativePrompt", ""),
                )
                image_bytes = await self._comfyui.run_workflow(workflow)

                storage_path = f"projects/{project_id}/characters/{character_id}/reference.png"
                upload_url = await self._storage.get_upload_url(storage_path, "image/png")
                await self._storage.upload_file(upload_url, image_bytes, "image/png")

                await self._publisher.publish("visiobook.ai.reference.completed", {
                    "projectId": project_id,
                    "characterId": character_id,
                    "referenceImageUrl": storage_path,
                })
                logger.info("Character reference completed", extra={"character_id": character_id})
            except Exception as exc:
                logger.exception("Character reference failed", extra={"character_id": character_id})
                await self._publisher.publish("visiobook.ai.reference.failed", {
                    "executionId": execution_id,
                    "characterId": character_id,
                    "projectId": project_id,
                    "error": str(exc),
                })

        for loc in locations:
            location_id = loc["locationId"]
            try:
                workflow = flux_location.build(
                    location_description=loc["description"],
                    visual_style=book_style["visualStyle"],
                    negative_prompt=book_style.get("negativePrompt", ""),
                )
                image_bytes = await self._comfyui.run_workflow(workflow)

                storage_path = f"projects/{project_id}/locations/{location_id}/reference.png"
                upload_url = await self._storage.get_upload_url(storage_path, "image/png")
                await self._storage.upload_file(upload_url, image_bytes, "image/png")

                await self._publisher.publish("visiobook.ai.reference.completed", {
                    "projectId": project_id,
                    "locationId": location_id,
                    "referenceImageUrl": storage_path,
                })
                logger.info("Location reference completed", extra={"location_id": location_id})
            except Exception as exc:
                logger.exception("Location reference failed", extra={"location_id": location_id})
                await self._publisher.publish("visiobook.ai.reference.failed", {
                    "executionId": execution_id,
                    "locationId": location_id,
                    "projectId": project_id,
                    "error": str(exc),
                })

        await self._publisher.publish("visiobook.ai.progress", {
            "executionId": execution_id,
            "step": "reference_generation",
            "progress": 10,
            "message": f"All references done: {len(characters)} character(s) + {len(locations)} location(s)",
        })
