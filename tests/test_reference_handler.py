import pytest

from app.handlers.reference_handler import ReferenceHandler


@pytest.fixture
def handler(comfyui, publisher, storage, settings):
    return ReferenceHandler(comfyui, publisher, storage, settings)


def _base_data(**overrides):
    base = {
        "userId": "user1",
        "projectId": "proj1",
        "executionId": "exec-1",
        "characters": [],
        "locations": [],
    }
    base.update(overrides)
    return base


class TestEmptyInput:
    async def test_only_progress_events_published(self, handler, publisher):
        await handler.handle(_base_data())
        assert publisher.subjects == [
            "visiobook.ai.progress",
            "visiobook.ai.progress",
        ]


class TestCharacters:
    async def test_success_publishes_completed_with_path(
        self, handler, publisher, storage
    ):
        await handler.handle(
            _base_data(characters=[{"characterId": "luna", "portraitPrompt": "a girl"}])
        )
        completed = publisher.by_subject("visiobook.ai.reference.completed")
        assert len(completed) == 1
        assert completed[0]["characterId"] == "luna"
        assert completed[0]["projectId"] == "proj1"
        assert completed[0]["referenceImageUrl"] == (
            "user1/proj1/characters/luna/reference.png"
        )
        # File was uploaded to storage
        assert "user1/proj1/characters/luna/reference.png" in storage.files

    async def test_comfyui_failure_publishes_failed_and_continues(
        self, handler, publisher, comfyui
    ):
        comfyui.responses = [RuntimeError("boom"), b"ok-bytes"]
        await handler.handle(
            _base_data(
                characters=[
                    {"characterId": "luna", "portraitPrompt": "p"},
                    {"characterId": "kai", "portraitPrompt": "p"},
                ]
            )
        )
        failed = publisher.by_subject("visiobook.ai.reference.failed")
        completed = publisher.by_subject("visiobook.ai.reference.completed")
        assert len(failed) == 1 and failed[0]["characterId"] == "luna"
        assert failed[0]["error"] == "boom"
        assert len(completed) == 1 and completed[0]["characterId"] == "kai"


class TestLocations:
    async def test_success_publishes_completed_with_path(
        self, handler, publisher, storage
    ):
        await handler.handle(
            _base_data(
                locations=[
                    {"locationId": "forest", "descriptionPrompt": "a misty wood"}
                ]
            )
        )
        completed = publisher.by_subject("visiobook.ai.reference.completed")
        assert len(completed) == 1
        assert completed[0]["locationId"] == "forest"
        assert completed[0]["referenceImageUrl"] == (
            "user1/proj1/locations/forest/reference.png"
        )
        assert "user1/proj1/locations/forest/reference.png" in storage.files

    async def test_failure_does_not_block_subsequent_locations(
        self, handler, publisher, comfyui
    ):
        comfyui.responses = [b"ok", RuntimeError("nope")]
        await handler.handle(
            _base_data(
                locations=[
                    {"locationId": "a", "descriptionPrompt": "p"},
                    {"locationId": "b", "descriptionPrompt": "p"},
                ]
            )
        )
        completed = publisher.by_subject("visiobook.ai.reference.completed")
        failed = publisher.by_subject("visiobook.ai.reference.failed")
        assert [c["locationId"] for c in completed] == ["a"]
        assert [f["locationId"] for f in failed] == ["b"]


class TestProgressBoundary:
    async def test_first_and_last_event_are_progress(self, handler, publisher):
        await handler.handle(
            _base_data(
                characters=[{"characterId": "x", "portraitPrompt": "p"}],
                locations=[{"locationId": "y", "descriptionPrompt": "p"}],
            )
        )
        assert publisher.published[0][0] == "visiobook.ai.progress"
        assert publisher.published[0][1]["progress"] == 5
        assert publisher.published[-1][0] == "visiobook.ai.progress"
        assert publisher.published[-1][1]["progress"] == 10
