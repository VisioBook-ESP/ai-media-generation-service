import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE_DIR = Path("outputs")


class LocalStorageClient:
    """Local filesystem storage for development. Paths map directly to disk."""

    async def get_upload_url(self, path: str, content_type: str) -> str:
        local_path = _BASE_DIR / path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        return str(local_path)

    async def upload_file(self, upload_url: str, data: bytes, content_type: str) -> None:
        dest = Path(upload_url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.info("File saved locally", extra={"path": str(dest)})

    async def read_file(self, path: str) -> bytes:
        return (_BASE_DIR / path).read_bytes()

    async def download_file(self, path: str, local_path: str) -> None:
        shutil.copy2(_BASE_DIR / path, local_path)
