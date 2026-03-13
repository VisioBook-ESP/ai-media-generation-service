import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

_BASE_DIR = Path("outputs")

_PATTERNS = [
    (re.compile(r"^projects/[^/]+/characters/(.+)$"), "images/characters"),
    (re.compile(r"^projects/[^/]+/locations/(.+)$"),  "images/locations"),
    (re.compile(r"^projects/[^/]+/scenes/(.+)$"),     "images/scenes"),
]


def _resolve(path: str) -> Path:
    for pattern, prefix in _PATTERNS:
        m = pattern.match(path)
        if m:
            return _BASE_DIR / prefix / m.group(1)
    return _BASE_DIR / path


class LocalStorageClient:
    async def get_upload_url(self, path: str, content_type: str) -> str:
        local_path = _resolve(path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        return str(local_path)

    async def upload_file(self, upload_url: str, data: bytes, content_type: str) -> None:
        dest = Path(upload_url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.info("File saved locally", extra={"path": str(dest)})

    async def read_file(self, path: str) -> bytes:
        return _resolve(path).read_bytes()

    async def download_file(self, path: str, local_path: str) -> None:
        src = _resolve(path)
        shutil.copy2(src, local_path)
