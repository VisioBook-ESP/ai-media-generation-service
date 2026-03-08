import logging
import httpx

logger = logging.getLogger(__name__)


class StorageServiceClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")

    async def get_upload_url(self, path: str, content_type: str) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{self._base_url}/upload-url",
                json={"path": path, "contentType": content_type},
            )
            response.raise_for_status()
            return response.json()["uploadUrl"]

    async def upload_file(self, upload_url: str, data: bytes, content_type: str) -> None:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.put(
                upload_url,
                content=data,
                headers={"Content-Type": content_type},
            )
            response.raise_for_status()

    async def download_file(self, path: str, local_path: str) -> None:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(f"{self._base_url}/download", params={"path": path})
            response.raise_for_status()
            content = response.content

        with open(local_path, "wb") as f:
            f.write(content)
