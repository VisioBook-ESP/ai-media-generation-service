import json

import pytest

from app.workflows import common


@pytest.fixture
def clear_template_cache():
    common._TEMPLATES.clear()
    yield
    common._TEMPLATES.clear()


@pytest.fixture
def fake_templates_dir(tmp_path, monkeypatch, clear_template_cache):
    monkeypatch.setattr(common, "_TEMPLATES_DIR", tmp_path)
    return tmp_path


class TestDeterministicSeed:
    def test_is_reproducible(self):
        assert common.deterministic_seed("scene_42") == common.deterministic_seed(
            "scene_42"
        )

    def test_different_keys_yield_different_seeds(self):
        assert common.deterministic_seed("a") != common.deterministic_seed("b")

    def test_multi_key_concatenation(self):
        # the implementation joins keys with ":" — order matters
        assert common.deterministic_seed("a", "b") != common.deterministic_seed(
            "b", "a"
        )

    def test_within_uint32_range(self):
        seed = common.deterministic_seed("anything")
        assert 0 <= seed < 2**32


class TestRandomSeed:
    def test_within_uint32_range(self):
        for _ in range(20):
            seed = common.random_seed()
            assert 0 <= seed < 2**32


class TestLoadTemplate:
    def test_returns_deepcopy_so_mutations_dont_leak(self, fake_templates_dir):
        (fake_templates_dir / "t.json").write_text(json.dumps({"6": {"inputs": {}}}))

        first = common.load_template("t.json", {"6"})
        first["6"]["inputs"]["text"] = "mutated"

        second = common.load_template("t.json", {"6"})
        assert second["6"]["inputs"] == {}

    def test_caches_after_first_read(self, fake_templates_dir):
        path = fake_templates_dir / "t.json"
        path.write_text(json.dumps({"6": {}}))

        common.load_template("t.json", {"6"})
        # Mutate file on disk; cached version should still be served
        path.write_text(json.dumps({"6": {}, "99": {}}))

        cached = common.load_template("t.json", {"6"})
        assert "99" not in cached

    def test_raises_keyerror_when_required_node_missing(self, fake_templates_dir):
        (fake_templates_dir / "t.json").write_text(json.dumps({"6": {}}))

        with pytest.raises(KeyError, match="missing nodes.*10"):
            common.load_template("t.json", {"6", "10"})

    def test_raises_filenotfound_when_template_missing(self, fake_templates_dir):
        with pytest.raises(FileNotFoundError):
            common.load_template("does_not_exist.json", set())
