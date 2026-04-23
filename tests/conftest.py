import pytest


class FakePublisher:
    """Captures (subject, data) tuples in the order they are published."""

    def __init__(self):
        self.published: list[tuple[str, dict]] = []

    async def publish(self, subject: str, data: dict) -> None:
        self.published.append((subject, data))

    @property
    def subjects(self) -> list[str]:
        return [s for s, _ in self.published]

    def by_subject(self, subject: str) -> list[dict]:
        return [d for s, d in self.published if s == subject]


class FakeComfyUI:
    """Returns canned responses; can be primed with a queue of bytes/Exceptions."""

    def __init__(self, default_response: bytes = b"img-bytes"):
        self.default_response = default_response
        self.responses: list = []  # bytes | Exception, consumed in order
        self.calls: list[dict] = []

    async def run_workflow(self, workflow, images=None, output_type: str = "image"):
        self.calls.append(
            {"workflow": workflow, "images": images, "output_type": output_type}
        )
        if self.responses:
            r = self.responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        return self.default_response


class FakeStorage:
    """In-memory storage. Upload urls are `mem://<path>`."""

    def __init__(self):
        self.files: dict[str, bytes] = {}

    async def get_upload_url(self, path: str, content_type: str) -> str:
        return f"mem://{path}"

    async def upload_file(
        self, upload_url: str, data: bytes, content_type: str
    ) -> None:
        path = upload_url.removeprefix("mem://")
        self.files[path] = data

    async def read_file(self, path: str) -> bytes:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def download_file(self, path: str, local_path: str) -> None:
        from pathlib import Path

        Path(local_path).write_bytes(await self.read_file(path))


@pytest.fixture
def publisher():
    return FakePublisher()


@pytest.fixture
def comfyui():
    return FakeComfyUI()


@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def settings():
    """Minimal settings stub — handlers only read attributes if needed."""

    class _S:
        ENV = "development"

    return _S()
