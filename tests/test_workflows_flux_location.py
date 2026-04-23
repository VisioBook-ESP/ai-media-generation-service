from app.workflows import common, flux_location


class TestFluxLocationBuild:
    def test_positive_prompt_injected_in_node_6(self):
        wf = flux_location.build(location_prompt="a misty forest")
        assert wf["6"]["inputs"]["text"] == "a misty forest"

    def test_default_negatives_exclude_people(self):
        wf = flux_location.build(location_prompt="x")
        assert "people" in wf["33"]["inputs"]["text"]
        assert "characters" in wf["33"]["inputs"]["text"]

    def test_user_negative_appended_to_defaults(self):
        wf = flux_location.build(location_prompt="x", negative_prompt="dark, horror")
        assert wf["33"]["inputs"]["text"].endswith("dark, horror")

    def test_location_id_yields_deterministic_seed(self):
        wf1 = flux_location.build(location_prompt="x", location_id="forest")
        wf2 = flux_location.build(location_prompt="x", location_id="forest")
        assert wf1["10"]["inputs"]["noise_seed"] == wf2["10"]["inputs"]["noise_seed"]
        assert wf1["10"]["inputs"]["noise_seed"] == common.deterministic_seed("forest")

    def test_no_location_id_yields_random_seed(self):
        wf = flux_location.build(location_prompt="x")
        seed = wf["10"]["inputs"]["noise_seed"]
        assert isinstance(seed, int) and 0 <= seed < 2**32
