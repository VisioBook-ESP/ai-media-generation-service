from app.workflows import common, flux_portrait


class TestFluxPortraitBuild:
    def test_positive_prompt_injected_in_node_6(self):
        wf = flux_portrait.build(portrait_prompt="a knight on a horse")
        assert wf["6"]["inputs"]["text"] == "a knight on a horse"

    def test_default_negatives_present_when_no_user_negative(self):
        wf = flux_portrait.build(portrait_prompt="x")
        assert "cropped body" in wf["33"]["inputs"]["text"]
        assert "multiple characters" in wf["33"]["inputs"]["text"]
        # no trailing comma when no extra negative
        assert not wf["33"]["inputs"]["text"].rstrip().endswith(",")

    def test_user_negative_appended_to_defaults(self):
        wf = flux_portrait.build(
            portrait_prompt="x", negative_prompt="ugly, bad anatomy"
        )
        text = wf["33"]["inputs"]["text"]
        assert "cropped body" in text
        assert text.endswith("ugly, bad anatomy")

    def test_character_id_yields_deterministic_seed(self):
        wf1 = flux_portrait.build(portrait_prompt="x", character_id="luna")
        wf2 = flux_portrait.build(portrait_prompt="x", character_id="luna")
        assert wf1["10"]["inputs"]["noise_seed"] == wf2["10"]["inputs"]["noise_seed"]
        assert wf1["10"]["inputs"]["noise_seed"] == common.deterministic_seed("luna")

    def test_no_character_id_yields_random_seed_in_uint32_range(self):
        wf = flux_portrait.build(portrait_prompt="x")
        seed = wf["10"]["inputs"]["noise_seed"]
        assert isinstance(seed, int) and 0 <= seed < 2**32
