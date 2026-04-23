from app.workflows import common, scene


async def fake_loader(url: str) -> str:
    return f"B64({url})"


class TestSceneBuildModeSelection:
    async def test_no_refs_uses_text_mode(self):
        wf, images, mode = await scene.build(
            scene_prompt="a dragon flies",
            visual_style="watercolor",
            load_image_b64=fake_loader,
        )
        assert mode == "text"
        assert images == []
        assert "a dragon flies" in wf["6"]["inputs"]["text"]
        assert "watercolor" in wf["6"]["inputs"]["text"]

    async def test_character_only_uses_character_mode(self):
        wf, images, mode = await scene.build(
            scene_prompt="x",
            visual_style="",
            load_image_b64=fake_loader,
            character_ref_url="path/to/char.png",
        )
        assert mode == "character"
        assert images == [{"name": "character.png", "image": "B64(path/to/char.png)"}]
        assert wf["11"]["inputs"]["strength"] == 0.35

    async def test_location_only_uses_location_mode(self):
        wf, images, mode = await scene.build(
            scene_prompt="x",
            visual_style="",
            load_image_b64=fake_loader,
            location_ref_url="path/to/loc.png",
        )
        assert mode == "location"
        assert images == [{"name": "reference.png", "image": "B64(path/to/loc.png)"}]
        assert wf["11"]["inputs"]["strength"] == 0.5

    async def test_both_refs_use_dual_redux_mode(self):
        wf, images, mode = await scene.build(
            scene_prompt="x",
            visual_style="",
            load_image_b64=fake_loader,
            character_ref_url="c.png",
            location_ref_url="l.png",
        )
        assert mode == "character_location"
        assert images == [
            {"name": "character.png", "image": "B64(c.png)"},
            {"name": "location.png", "image": "B64(l.png)"},
        ]


class TestScenePromptComposition:
    async def test_visual_style_appended_to_positive(self):
        wf, _, _ = await scene.build(
            scene_prompt="a wolf",
            visual_style="ghibli style",
            load_image_b64=fake_loader,
        )
        text = wf["6"]["inputs"]["text"]
        assert "a wolf" in text and "ghibli style" in text

    async def test_no_visual_style_omits_style_segment(self):
        wf, _, _ = await scene.build(
            scene_prompt="a wolf",
            visual_style="",
            load_image_b64=fake_loader,
        )
        # text mode doesn't carry negative; just check positive structure
        text = wf["6"]["inputs"]["text"]
        assert text.startswith("a wolf, ")
        assert "consistent storybook style" in text

    async def test_negative_default_in_redux_mode(self):
        wf, _, _ = await scene.build(
            scene_prompt="x",
            visual_style="",
            load_image_b64=fake_loader,
            character_ref_url="c.png",
        )
        # Single-redux uses node "9" for negative
        assert "duplicate character" in wf["9"]["inputs"]["text"]

    async def test_user_negative_appended_in_redux_mode(self):
        wf, _, _ = await scene.build(
            scene_prompt="x",
            visual_style="",
            negative_prompt="blurry",
            load_image_b64=fake_loader,
            location_ref_url="l.png",
        )
        assert wf["9"]["inputs"]["text"].endswith("blurry")


class TestSceneSeed:
    async def test_scene_id_yields_deterministic_seed_text_mode(self):
        wf1, *_ = await scene.build(
            scene_prompt="x",
            visual_style="",
            load_image_b64=fake_loader,
            scene_id="scene_0",
        )
        wf2, *_ = await scene.build(
            scene_prompt="x",
            visual_style="",
            load_image_b64=fake_loader,
            scene_id="scene_0",
        )
        assert wf1["10"]["inputs"]["noise_seed"] == wf2["10"]["inputs"]["noise_seed"]
        assert wf1["10"]["inputs"]["noise_seed"] == common.deterministic_seed("scene_0")

    async def test_scene_id_seed_used_in_redux_node_20(self):
        wf, *_ = await scene.build(
            scene_prompt="x",
            visual_style="",
            load_image_b64=fake_loader,
            character_ref_url="c.png",
            scene_id="scene_1",
        )
        assert wf["20"]["inputs"]["noise_seed"] == common.deterministic_seed("scene_1")

    async def test_no_scene_id_yields_random_seed(self):
        wf, *_ = await scene.build(
            scene_prompt="x",
            visual_style="",
            load_image_b64=fake_loader,
        )
        seed = wf["10"]["inputs"]["noise_seed"]
        assert isinstance(seed, int) and 0 <= seed < 2**32

    async def test_loader_not_called_in_text_mode(self):
        calls = []

        async def tracking_loader(url):
            calls.append(url)
            return "B64"

        await scene.build(
            scene_prompt="x", visual_style="", load_image_b64=tracking_loader
        )
        assert calls == []

    async def test_loader_called_once_per_ref_in_dual_mode(self):
        calls = []

        async def tracking_loader(url):
            calls.append(url)
            return f"B64({url})"

        await scene.build(
            scene_prompt="x",
            visual_style="",
            load_image_b64=tracking_loader,
            character_ref_url="c.png",
            location_ref_url="l.png",
        )
        assert calls == ["c.png", "l.png"]
