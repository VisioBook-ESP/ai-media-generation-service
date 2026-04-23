import base64

import pytest

from app.handlers.webhook_handler import WebhookHandler


@pytest.fixture
def handler(storage, publisher):
    return WebhookHandler(storage=storage, publisher=publisher)


def _png_b64() -> str:
    return base64.b64encode(b"PNGDATA").decode()


def _completed_body(job_type: str, **metadata_overrides):
    metadata = {
        "user_id": "u",
        "project_id": "p",
        "job_type": job_type,
        **metadata_overrides,
    }
    return {
        "id": "job-123",
        "status": "COMPLETED",
        "input": {"metadata": metadata},
        "output": {"images": [{"type": "base64", "data": _png_b64()}]},
    }


class TestCompletedRouting:
    async def test_character_reference_uploads_and_publishes(
        self, handler, publisher, storage
    ):
        await handler.handle(
            _completed_body("character_reference", character_id="luna")
        )
        completed = publisher.by_subject("visiobook.ai.reference.completed")
        assert len(completed) == 1
        assert completed[0]["characterId"] == "luna"
        assert completed[0]["referenceImageUrl"] == (
            "u/p/characters/luna/reference.png"
        )
        assert storage.files["u/p/characters/luna/reference.png"] == b"PNGDATA"

    async def test_location_reference_uploads_and_publishes(
        self, handler, publisher, storage
    ):
        await handler.handle(
            _completed_body("location_reference", location_id="forest")
        )
        completed = publisher.by_subject("visiobook.ai.reference.completed")
        assert len(completed) == 1
        assert completed[0]["locationId"] == "forest"
        assert storage.files["u/p/locations/forest/reference.png"] == b"PNGDATA"

    async def test_scene_image_uploads_and_publishes(self, handler, publisher, storage):
        body = _completed_body("scene_image", scene_id="scene_0", execution_id="exec-9")
        await handler.handle(body)
        completed = publisher.by_subject("visiobook.ai.media.image.completed")
        assert completed[0]["sceneId"] == "scene_0"
        assert completed[0]["executionId"] == "exec-9"
        assert completed[0]["mediaUrl"] == "u/p/scenes/scene_0/image.png"

    async def test_unknown_job_type_publishes_nothing(self, handler, publisher):
        await handler.handle(_completed_body("mystery_job", scene_id="s"))
        assert publisher.published == []


class TestFailedRouting:
    async def test_character_failure_publishes_reference_failed(
        self, handler, publisher
    ):
        body = {
            "id": "j",
            "status": "FAILED",
            "input": {
                "metadata": {
                    "job_type": "character_reference",
                    "user_id": "u",
                    "project_id": "p",
                    "character_id": "luna",
                    "execution_id": "e",
                }
            },
            "error": "OOM",
        }
        await handler.handle(body)
        failed = publisher.by_subject("visiobook.ai.reference.failed")
        assert len(failed) == 1
        assert failed[0]["characterId"] == "luna"
        assert failed[0]["error"] == "OOM"

    async def test_location_failure_publishes_reference_failed(
        self, handler, publisher
    ):
        body = {
            "id": "j",
            "status": "FAILED",
            "input": {
                "metadata": {
                    "job_type": "location_reference",
                    "project_id": "p",
                    "location_id": "forest",
                }
            },
            "error": "boom",
        }
        await handler.handle(body)
        failed = publisher.by_subject("visiobook.ai.reference.failed")
        assert failed[0]["locationId"] == "forest"

    async def test_scene_failure_publishes_media_failed(self, handler, publisher):
        body = {
            "id": "j",
            "status": "FAILED",
            "input": {"metadata": {"job_type": "scene_image", "scene_id": "scene_0"}},
            "error": "crash",
        }
        await handler.handle(body)
        failed = publisher.by_subject("visiobook.ai.media.failed")
        assert failed[0]["sceneId"] == "scene_0"


class TestIgnoredStatus:
    async def test_in_progress_status_publishes_nothing(self, handler, publisher):
        await handler.handle(
            {"id": "j", "status": "IN_PROGRESS", "input": {"metadata": {}}}
        )
        assert publisher.published == []


class TestExtractImageBytes:
    async def test_no_images_raises_value_error(self, handler):
        with pytest.raises(ValueError, match="no images"):
            await handler._extract_image_bytes({"images": []})

    async def test_unsupported_type_raises_value_error(self, handler):
        with pytest.raises(ValueError, match="Unsupported"):
            await handler._extract_image_bytes(
                {"images": [{"type": "url", "data": "https://..."}]}
            )

    async def test_base64_decoded_correctly(self, handler):
        b64 = base64.b64encode(b"hello").decode()
        result = await handler._extract_image_bytes(
            {"images": [{"type": "base64", "data": b64}]}
        )
        assert result == b"hello"
