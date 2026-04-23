from app import storage_paths
from app.storage_paths import _slugify


class TestSlugify:
    def test_lowercases_and_replaces_spaces(self):
        assert _slugify("Hello World") == "hello_world"

    def test_collapses_special_chars(self):
        assert _slugify("Foo!!! Bar??") == "foo_bar"

    def test_strips_edge_underscores(self):
        assert _slugify("__hello__") == "hello"

    def test_accents_are_dropped(self):
        # accents are not in [a-z0-9] and become separators
        assert _slugify("Éloïse") == "lo_se"

    def test_empty_returns_unnamed(self):
        assert _slugify("") == "unnamed"

    def test_only_punctuation_returns_unnamed(self):
        assert _slugify("!!!") == "unnamed"

    def test_already_slug_unchanged(self):
        assert _slugify("foo_bar_42") == "foo_bar_42"


class TestPaths:
    def test_character_ref_format(self):
        path = storage_paths.character_ref("user1", "proj1", "Luna")
        assert path == "user1/proj1/characters/luna/reference.png"

    def test_character_ref_slugifies_name(self):
        path = storage_paths.character_ref("u", "p", "Big Bad Wolf!")
        assert path == "u/p/characters/big_bad_wolf/reference.png"

    def test_location_ref_uses_id_verbatim(self):
        # locations use raw id (no slugify)
        path = storage_paths.location_ref("u", "p", "enchanted_forest")
        assert path == "u/p/locations/enchanted_forest/reference.png"

    def test_scene_image_format(self):
        path = storage_paths.scene_image("u", "p", "scene_3")
        assert path == "u/p/scenes/scene_3/image.png"

    def test_animated_scene_format(self):
        path = storage_paths.animated_scene("u", "p", "scene_3")
        assert path == "u/p/animated_scenes/scene_3/animation.mp4"
