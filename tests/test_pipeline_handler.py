import pytest

from app.handlers.pipeline_handler import PipelineHandler


@pytest.fixture
def handler(comfyui, publisher, storage, settings):
    return PipelineHandler(comfyui, publisher, storage, settings)


def _data(characters=None, locations=None, scenes=None):
    return {
        "userId": "u",
        "projectId": "p",
        "executionId": "exec-1",
        "characters": characters or [],
        "locations": locations or [],
        "scenes": scenes or [],
    }


class TestEmptyPipeline:
    async def test_only_progress_and_pipeline_completed(self, handler, publisher):
        await handler.handle(_data())
        assert "visiobook.ai.pipeline.completed" in publisher.subjects
        # No reference/media events when there's nothing to generate
        assert publisher.by_subject("visiobook.ai.reference.completed") == []
        assert publisher.by_subject("visiobook.ai.media.image.completed") == []

    async def test_pipeline_completed_payload_contains_ids(self, handler, publisher):
        await handler.handle(_data())
        done = publisher.by_subject("visiobook.ai.pipeline.completed")
        assert done == [{"executionId": "exec-1", "projectId": "p"}]


class TestHappyPath:
    async def test_full_one_of_each_phase(self, handler, publisher, storage):
        await handler.handle(
            _data(
                characters=[
                    {"name": "Luna", "portraitPrompt": "a girl"},
                ],
                locations=[
                    {"locationId": "forest", "descriptionPrompt": "a wood"},
                ],
                scenes=[
                    {
                        "order": 0,
                        "imagePrompt": "luna in forest",
                        "charactersPresent": ["Luna"],
                        "locationId": "forest",
                        "duration": 3,
                    }
                ],
            )
        )
        # Phase 1: character ref
        refs = publisher.by_subject("visiobook.ai.reference.completed")
        assert any("characterName" in r for r in refs)
        assert any("locationId" in r for r in refs)
        # Phase 3: scene image
        images = publisher.by_subject("visiobook.ai.media.image.completed")
        assert len(images) == 1
        assert images[0]["sceneOrder"] == 0
        assert images[0]["mode"] == "character_location"
        # Phase 4: animation
        anims = publisher.by_subject("visiobook.ai.media.animation.completed")
        assert len(anims) == 1
        # Final: pipeline completed
        assert publisher.subjects[-1] == "visiobook.ai.pipeline.completed"

        # Storage was populated at each phase
        assert "u/p/characters/luna/reference.png" in storage.files
        assert "u/p/locations/forest/reference.png" in storage.files
        assert "u/p/scenes/scene_0/image.png" in storage.files
        assert "u/p/animated_scenes/scene_0/animation.mp4" in storage.files


class TestErrorIsolation:
    async def test_character_failure_publishes_failed_and_pipeline_continues(
        self, handler, publisher, comfyui
    ):
        # First char fails, second succeeds
        comfyui.responses = [RuntimeError("nope"), b"ok"]
        await handler.handle(
            _data(
                characters=[
                    {"name": "A", "portraitPrompt": "p"},
                    {"name": "B", "portraitPrompt": "p"},
                ]
            )
        )
        failed = publisher.by_subject("visiobook.ai.reference.failed")
        completed = publisher.by_subject("visiobook.ai.reference.completed")
        assert [f["characterName"] for f in failed] == ["A"]
        assert [c["characterName"] for c in completed] == ["B"]
        # Pipeline still finishes
        assert publisher.subjects[-1] == "visiobook.ai.pipeline.completed"

    async def test_scene_failure_does_not_kill_animation_phase(
        self, handler, publisher, comfyui
    ):
        # 2 scenes: first fails on image, second succeeds; only the second triggers animation
        comfyui.responses = [RuntimeError("scene-down"), b"img-ok", b"video-ok"]
        await handler.handle(
            _data(
                scenes=[
                    {"order": 0, "imagePrompt": "x"},
                    {"order": 1, "imagePrompt": "y"},
                ]
            )
        )
        media_failed = publisher.by_subject("visiobook.ai.media.failed")
        media_completed = publisher.by_subject("visiobook.ai.media.image.completed")
        anims = publisher.by_subject("visiobook.ai.media.animation.completed")
        assert [f["sceneOrder"] for f in media_failed] == [0]
        assert [c["sceneOrder"] for c in media_completed] == [1]
        assert len(anims) == 1
        assert publisher.subjects[-1] == "visiobook.ai.pipeline.completed"


class TestSceneOrdering:
    async def test_scenes_processed_in_order_field_not_input_order(
        self, handler, publisher
    ):
        await handler.handle(
            _data(
                scenes=[
                    {"order": 2, "imagePrompt": "z"},
                    {"order": 0, "imagePrompt": "x"},
                    {"order": 1, "imagePrompt": "y"},
                ]
            )
        )
        images = publisher.by_subject("visiobook.ai.media.image.completed")
        assert [i["sceneOrder"] for i in images] == [0, 1, 2]


class TestCharacterMissingFromMap:
    async def test_scene_with_unknown_character_falls_back_to_text_mode(
        self, handler, publisher
    ):
        # No characters generated, but scene mentions one — char_ref_paths.get returns None
        await handler.handle(
            _data(
                scenes=[
                    {
                        "order": 0,
                        "imagePrompt": "x",
                        "charactersPresent": ["Ghost"],
                    }
                ]
            )
        )
        images = publisher.by_subject("visiobook.ai.media.image.completed")
        assert images[0]["mode"] == "text"
