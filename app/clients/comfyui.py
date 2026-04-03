import asyncio
import logging
import uuid
from io import BytesIO

import httpx

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2.0
_POLL_TIMEOUT = 600.0


class ComfyUIClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    async def run_workflow(
        self, workflow: dict, images: list[dict] | None = None, output_type: str = "image"
    ) -> bytes:
        timeout = 120 if output_type == "image" else 600
        async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
            if images:
                for img in images:
                    await self._upload_image(client, img["name"], img["image"])

            prompt_id = await self._queue_prompt(client, workflow)
            output = await self._poll_until_done(client, prompt_id)
            return await self._download_output(client, output, output_type)

    async def _upload_image(
        self, client: httpx.AsyncClient, name: str, b64_data: str
    ) -> None:
        import base64

        raw = base64.b64decode(b64_data)
        files = {"image": (name, BytesIO(raw), "image/png")}
        data = {"overwrite": "true"}
        resp = await client.post("/upload/image", files=files, data=data)
        resp.raise_for_status()
        logger.debug("Uploaded image %s to ComfyUI", name)

    async def _queue_prompt(
        self, client: httpx.AsyncClient, workflow: dict
    ) -> str:
        client_id = uuid.uuid4().hex
        payload = {"prompt": workflow, "client_id": client_id}
        resp = await client.post("/prompt", json=payload)
        if resp.status_code != 200:
            logger.error("ComfyUI prompt rejected: %s", resp.text)
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]
        logger.info("ComfyUI prompt queued", extra={"prompt_id": prompt_id})
        return prompt_id

    async def _poll_until_done(
        self, client: httpx.AsyncClient, prompt_id: str
    ) -> dict:
        elapsed = 0.0
        while elapsed < _POLL_TIMEOUT:
            resp = await client.get(f"/history/{prompt_id}")
            if resp.status_code == 404:
                await asyncio.sleep(_POLL_INTERVAL)
                elapsed += _POLL_INTERVAL
                continue
            resp.raise_for_status()
            history = resp.json()

            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                outputs = entry.get("outputs", {})
                if status.get("completed") or (outputs and status.get("status_str") == "success"):
                    logger.info("ComfyUI prompt completed", extra={"prompt_id": prompt_id})
                    return outputs
                status_msg = status.get("status_str", "")
                if "error" in status_msg.lower():
                    raise RuntimeError(f"ComfyUI prompt failed: {status_msg}")

            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

        raise TimeoutError(f"ComfyUI prompt {prompt_id} timed out after {_POLL_TIMEOUT}s")

    async def _download_output(
        self, client: httpx.AsyncClient, outputs: dict, output_type: str = "image"
    ) -> bytes:
        for node_id, node_output in outputs.items():
            # ComfyUI stores animated WEBP in "gifs" key, images in "images" key
            candidates = node_output.get("gifs", []) or node_output.get("images", [])
            if candidates:
                item = candidates[0]
                filename = item["filename"]
                subfolder = item.get("subfolder", "")
                folder_type = item.get("type", "output")
                resp = await client.get(
                    "/view",
                    params={
                        "filename": filename,
                        "subfolder": subfolder,
                        "type": folder_type,
                    },
                )
                resp.raise_for_status()
                logger.info("Downloaded output %s: %s", output_type, filename)
                return resp.content

        raise ValueError(f"No output {output_type}s found in ComfyUI response")
