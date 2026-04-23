import logging
import httpx

logger = logging.getLogger(__name__)

RUNPOD_API_BASE = "https://api.runpod.ai/v2"


class RunPodClient:
    def __init__(self, api_key: str, webhook_base_url: str):
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._webhook_base_url = webhook_base_url.rstrip("/")

    async def submit_job(
        self,
        endpoint_id: str,
        workflow: dict,
        metadata: dict,
        images: list | None = None,
    ) -> str:
        url = f"{RUNPOD_API_BASE}/{endpoint_id}/run"
        job_input: dict = {"workflow": workflow, "metadata": metadata}
        if images:
            job_input["images"] = images
        payload = {
            "input": job_input,
            "webhook": f"{self._webhook_base_url}/webhook/runpod",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
            data = response.json()

        job_id = data["id"]
        logger.info(
            "RunPod job submitted", extra={"job_id": job_id, "endpoint_id": endpoint_id}
        )
        return job_id
