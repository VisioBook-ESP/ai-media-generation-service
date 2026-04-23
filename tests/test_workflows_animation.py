import pytest

from app.workflows import animation, common


class TestClampDuration:
    def test_none_returns_default(self):
        assert animation._clamp_duration(None) == animation._DEFAULT_DURATION_SEC

    def test_below_min_clamped_up(self):
        assert animation._clamp_duration(0.5) == animation._MIN_DURATION_SEC

    def test_above_max_clamped_down(self):
        assert animation._clamp_duration(99) == animation._MAX_DURATION_SEC

    def test_in_range_passes_through(self):
        assert animation._clamp_duration(3.0) == 3.0

    def test_string_coerced_to_float(self):
        assert animation._clamp_duration(3) == 3.0


class TestLtxNumFrames:
    @pytest.mark.parametrize("duration", [2.0, 3.0, 4.0, 5.0, 6.0])
    def test_result_is_8n_plus_1_shape(self, duration):
        n = animation._ltx_num_frames(duration, 25)
        assert (n - 1) % 8 == 0

    def test_minimum_frame_count_is_at_least_9(self):
        # For very short durations, must clamp to ≥9 frames before 8n+1 rounding
        assert animation._ltx_num_frames(0.1, 25) >= 9

    def test_4s_at_25fps_rounds_to_nearest_8n_plus_1(self):
        # 4s * 25fps = 100 frames target → next 8n+1 ≥ 100 = 105
        assert animation._ltx_num_frames(4.0, 25) == 105


class TestAnimationBuild:
    def test_default_duration_used_when_none(self):
        wf, _ = animation.build(scene_prompt="x")
        expected_frames = animation._ltx_num_frames(
            animation._DEFAULT_DURATION_SEC, animation._ANIMATION_FPS
        )
        assert wf["267:225"]["inputs"]["value"] == expected_frames

    def test_fps_set_to_25(self):
        wf, _ = animation.build(scene_prompt="x")
        assert wf["267:260"]["inputs"]["value"] == animation._ANIMATION_FPS

    def test_prompt_with_visual_style_concatenated(self):
        wf, _ = animation.build(scene_prompt="a wolf runs", visual_style="ghibli")
        assert wf["267:266"]["inputs"]["value"] == "a wolf runs, ghibli"

    def test_prompt_without_visual_style(self):
        wf, _ = animation.build(scene_prompt="a wolf runs")
        assert wf["267:266"]["inputs"]["value"] == "a wolf runs"

    def test_negative_prompt_set(self):
        wf, _ = animation.build(scene_prompt="x")
        assert "static image" in wf["267:247"]["inputs"]["text"]

    def test_scene_id_yields_deterministic_seeds_offset_by_one(self):
        wf, _ = animation.build(scene_prompt="x", scene_id="scene_0")
        expected = common.deterministic_seed("scene_0", "animation")
        assert wf["267:237"]["inputs"]["noise_seed"] == expected
        assert wf["267:216"]["inputs"]["noise_seed"] == expected + 1

    def test_no_scene_id_yields_random_seed_in_uint32_range(self):
        wf, _ = animation.build(scene_prompt="x")
        seed = wf["267:237"]["inputs"]["noise_seed"]
        assert isinstance(seed, int) and 0 <= seed < 2**32

    def test_returns_image_placeholder(self):
        _, images = animation.build(scene_prompt="x")
        assert images == [{"name": "scene.png", "image": None}]

    def test_clamped_duration_used_for_frame_count(self):
        wf, _ = animation.build(scene_prompt="x", duration_sec=99)
        expected = animation._ltx_num_frames(
            animation._MAX_DURATION_SEC, animation._ANIMATION_FPS
        )
        assert wf["267:225"]["inputs"]["value"] == expected
