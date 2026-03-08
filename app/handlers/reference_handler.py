import logging
from app.workflows import flux_portrait, flux_location

logger = logging.getLogger(__name__)


class ReferenceHandler:
    def __init__(self, runpod, publisher, settings):
        self._runpod = runpod
        self._publisher = publisher
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
            workflow = flux_portrait.build(
                physical_description=char["physicalDescription"],
                visual_style=book_style["visualStyle"],
                negative_prompt=book_style.get("negativePrompt", ""),
            )
            job_id = await self._runpod.submit_job(
                endpoint_id=self._settings.RUNPOD_ENDPOINT_IMAGE,
                workflow=workflow,
                metadata={
                    "job_type": "character_reference",
                    "character_id": char["characterId"],
                    "project_id": project_id,
                    "execution_id": execution_id,
                },
            )
            logger.info("Character reference job submitted", extra={"job_id": job_id, "character_id": char["characterId"]})

        for loc in locations:
            workflow = flux_location.build(
                location_description=loc["description"],
                visual_style=book_style["visualStyle"],
                negative_prompt=book_style.get("negativePrompt", ""),
            )
            job_id = await self._runpod.submit_job(
                endpoint_id=self._settings.RUNPOD_ENDPOINT_IMAGE,
                workflow=workflow,
                metadata={
                    "job_type": "location_reference",
                    "location_id": loc["locationId"],
                    "project_id": project_id,
                    "execution_id": execution_id,
                },
            )
            logger.info("Location reference job submitted", extra={"job_id": job_id, "location_id": loc["locationId"]})

        await self._publisher.publish("visiobook.ai.progress", {
            "executionId": execution_id,
            "step": "reference_generation",
            "progress": 10,
            "message": f"All reference jobs queued: {len(characters)} character(s) + {len(locations)} location(s)",
        })
