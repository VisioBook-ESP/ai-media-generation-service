import base64

import pytest

from app.handlers.scene_handler import SceneHandler


@pytest.fixture
def handler(comfyui, publisher, storage, settings):
    return SceneHandler(comfyui, publisher, storage, settings)


def _data(scenes=None, **overrides):
    base = {
        "userId": "u",
        "projectId": "p",
        "executionId": "exec-1",
        "bookStyle": {"visualStyle": "watercolor", "negativePrompt": "ugly"},
        "scenes": scenes or [],
    }
    base.update(overrides)
    return base


def _scene(scene_id="scene_0", **extra):
    s = {"sceneId": scene_id, "prompt": {"image": "a wolf"}}
    s.update(extra)
    return s


class TestEmptyInput:
    async def test_only_progress_events(self, handler, publisher):
        await handler.handle(_data())
        assert publisher.subjects == [
            "visiobook.ai.progress",
            "visiobook.ai.progress",
        ]

    async def test_missing_book_style_raises(self, handler):
        bad = _data()
        del bad["bookStyle"]
        with pytest.raises(KeyError):
            await handler.handle(bad)


class TestTextModeScene:
    async def test_publishes_completed_with_scene_image_path(
        self, handler, publisher, storage
    ):
        await handler.handle(_data(scenes=[_scene("scene_0")]))
        completed = publisher.by_subject("visiobook.ai.media.image.completed")
        assert len(completed) == 1
        assert completed[0]["sceneId"] == "scene_0"
        assert completed[0]["mediaUrl"] == "u/p/scenes/scene_0/image.png"
        assert "u/p/scenes/scene_0/image.png" in storage.files


class TestRefModes:
    async def test_character_ref_loaded_from_storage_and_passed_to_comfyui(
        self, handler, comfyui, storage
    ):
        ref_path = "u/p/characters/luna/reference.png"
        storage.files[ref_path] = b"\x00CHAR"
        await handler.handle(
            _data(
                scenes=[
                    _scene(
                        "scene_0",
                        characterRef={"referenceImageUrl": ref_path},
                    )
                ]
            )
        )
        # Verify the character bytes were base64-encoded into the workflow's image payload
        call = comfyui.calls[0]
        assert call["images"] is not None
        assert call["images"][0]["name"] == "character.png"
        assert call["images"][0]["image"] == base64.b64encode(b"\x00CHAR").decode()

    async def test_dual_ref_loads_both_images(self, handler, comfyui, storage):
        char_path = "u/p/characters/luna/reference.png"
        loc_path = "u/p/locations/forest/reference.png"
        storage.files[char_path] = b"C"
        storage.files[loc_path] = b"L"
        await handler.handle(
            _data(
                scenes=[
                    _scene(
                        "scene_0",
                        characterRef={"referenceImageUrl": char_path},
                        locationRef={"referenceImageUrl": loc_path},
                    )
                ]
            )
        )
        names = [img["name"] for img in comfyui.calls[0]["images"]]
        assert names == ["character.png", "location.png"]


class TestErrorIsolation:
    async def test_one_scene_failure_does_not_stop_others(
        self, handler, publisher, comfyui
    ):
        comfyui.responses = [RuntimeError("comfy down"), b"ok"]
        await handler.handle(_data(scenes=[_scene("scene_0"), _scene("scene_1")]))
        failed = publisher.by_subject("visiobook.ai.media.failed")
        completed = publisher.by_subject("visiobook.ai.media.image.completed")
        assert [f["sceneId"] for f in failed] == ["scene_0"]
        assert [c["sceneId"] for c in completed] == ["scene_1"]
        assert failed[0]["error"] == "comfy down"
