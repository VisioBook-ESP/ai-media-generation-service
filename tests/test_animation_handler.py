import base64

import pytest

from app.handlers.animation_handler import AnimationHandler


@pytest.fixture
def handler(comfyui, publisher, storage, settings):
    return AnimationHandler(comfyui, publisher, storage, settings)


def _data(scenes=None):
    return {
        "userId": "u",
        "projectId": "p",
        "executionId": "exec-1",
        "scenes": scenes or [],
    }


class TestEmptyInput:
    async def test_only_progress_events(self, handler, publisher):
        await handler.handle(_data())
        assert publisher.subjects == [
            "visiobook.ai.progress",
            "visiobook.ai.progress",
        ]


class TestSkipBehavior:
    async def test_scene_without_image_url_is_skipped(
        self, handler, publisher, comfyui
    ):
        await handler.handle(_data(scenes=[{"sceneId": "scene_0"}]))
        # No completed/failed events, no comfyui calls
        assert publisher.by_subject("visiobook.ai.media.animation.completed") == []
        assert publisher.by_subject("visiobook.ai.media.failed") == []
        assert comfyui.calls == []


class TestSuccess:
    async def test_publishes_animation_completed(self, handler, publisher, storage):
        storage.files["u/p/scenes/scene_0/image.png"] = b"img"
        await handler.handle(
            _data(
                scenes=[
                    {
                        "sceneId": "scene_0",
                        "prompt": {"image": "a wolf runs"},
                        "sceneImageUrl": "u/p/scenes/scene_0/image.png",
                        "duration": 3,
                    }
                ]
            )
        )
        completed = publisher.by_subject("visiobook.ai.media.animation.completed")
        assert len(completed) == 1
        assert completed[0]["sceneId"] == "scene_0"
        assert completed[0]["mediaUrl"] == ("u/p/animated_scenes/scene_0/animation.mp4")
        assert "u/p/animated_scenes/scene_0/animation.mp4" in storage.files

    async def test_scene_image_loaded_as_base64_in_workflow_input(
        self, handler, comfyui, storage
    ):
        storage.files["u/p/scenes/scene_0/image.png"] = b"PIXELS"
        await handler.handle(
            _data(
                scenes=[
                    {
                        "sceneId": "scene_0",
                        "prompt": {"image": "x"},
                        "sceneImageUrl": "u/p/scenes/scene_0/image.png",
                    }
                ]
            )
        )
        call = comfyui.calls[0]
        assert call["output_type"] == "video"
        assert call["images"][0]["image"] == base64.b64encode(b"PIXELS").decode()


class TestErrorIsolation:
    async def test_failure_publishes_media_failed_and_continues(
        self, handler, publisher, comfyui, storage
    ):
        storage.files["a.png"] = b"a"
        storage.files["b.png"] = b"b"
        comfyui.responses = [RuntimeError("kaboom"), b"video-ok"]
        await handler.handle(
            _data(
                scenes=[
                    {
                        "sceneId": "scene_0",
                        "prompt": {"image": "x"},
                        "sceneImageUrl": "a.png",
                    },
                    {
                        "sceneId": "scene_1",
                        "prompt": {"image": "x"},
                        "sceneImageUrl": "b.png",
                    },
                ]
            )
        )
        failed = publisher.by_subject("visiobook.ai.media.failed")
        completed = publisher.by_subject("visiobook.ai.media.animation.completed")
        assert [f["sceneId"] for f in failed] == ["scene_0"]
        assert [c["sceneId"] for c in completed] == ["scene_1"]
        assert failed[0]["error"] == "kaboom"
