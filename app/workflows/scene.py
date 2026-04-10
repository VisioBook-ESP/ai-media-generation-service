from app.workflows.common import deterministic_seed, load_template, random_seed

_TEXT_NODES = {"6", "10"}
_REDUX_NODES = {"6", "8", "9", "20"}
_DUAL_REDUX_NODES = {"6", "7", "10", "11", "20"}

_SCENE_BASE_QUALITY = "single illustration frame, cinematic composition, consistent storybook style"
_SCENE_NEGATIVE = "duplicate character, extra limbs, bad anatomy, cropped subject, cut off hands, cut off feet"


def _positive(scene_prompt: str, visual_style: str = "") -> str:
    parts = [scene_prompt, _SCENE_BASE_QUALITY]
    if visual_style:
        parts.append(visual_style)
    return ", ".join(parts)


def _negative(negative_prompt: str) -> str:
    return f"{_SCENE_NEGATIVE}, {negative_prompt}" if negative_prompt else _SCENE_NEGATIVE


def _seed(scene_id: str | None) -> int:
    if scene_id:
        return deterministic_seed(scene_id)
    return random_seed()


def _build_text(scene_prompt: str, visual_style: str, negative_prompt: str, seed: int) -> tuple[dict, list[dict], str]:
    workflow = load_template("flux_scene.json", _TEXT_NODES)
    workflow["6"]["inputs"]["text"] = _positive(scene_prompt, visual_style)
    workflow["10"]["inputs"]["noise_seed"] = seed
    return workflow, [], "text"


def _build_redux(
    scene_prompt: str,
    visual_style: str,
    negative_prompt: str,
    ref_b64: str,
    seed: int,
    ref_name: str = "reference.png",
) -> tuple[dict, list[dict], str]:
    """Single Redux reference (location or character)."""
    workflow = load_template("flux_scene_redux.json", _REDUX_NODES)
    workflow["6"]["inputs"]["image"] = ref_name
    workflow["8"]["inputs"]["text"] = _positive(scene_prompt, visual_style)
    workflow["9"]["inputs"]["text"] = _negative(negative_prompt)
    workflow["20"]["inputs"]["noise_seed"] = seed
    return workflow, [{"name": ref_name, "image": ref_b64}]


def _build_location(
    scene_prompt: str, visual_style: str, negative_prompt: str, location_b64: str, seed: int,
) -> tuple[dict, list[dict], str]:
    workflow, images = _build_redux(scene_prompt, visual_style, negative_prompt, location_b64, seed, "reference.png")
    workflow["11"]["inputs"]["strength"] = 0.5
    return workflow, images, "location"


def _build_character(
    scene_prompt: str, visual_style: str, negative_prompt: str, character_b64: str, seed: int,
) -> tuple[dict, list[dict], str]:
    workflow, images = _build_redux(scene_prompt, visual_style, negative_prompt, character_b64, seed, "character.png")
    workflow["11"]["inputs"]["strength"] = 0.35
    return workflow, images, "character"


def _build_character_location(
    scene_prompt: str,
    visual_style: str,
    negative_prompt: str,
    character_b64: str,
    location_b64: str,
    seed: int,
) -> tuple[dict, list[dict], str]:
    """Dual Redux: character (0.25) + location (0.5)."""
    workflow = load_template("flux_scene_dual_redux.json", _DUAL_REDUX_NODES)
    workflow["6"]["inputs"]["image"] = "character.png"
    workflow["7"]["inputs"]["image"] = "location.png"
    workflow["10"]["inputs"]["text"] = _positive(scene_prompt, visual_style)
    workflow["11"]["inputs"]["text"] = _negative(negative_prompt)
    workflow["20"]["inputs"]["noise_seed"] = seed
    images = [
        {"name": "character.png", "image": character_b64},
        {"name": "location.png", "image": location_b64},
    ]
    return workflow, images, "character_location"


async def build(
    scene_prompt: str,
    visual_style: str,
    load_image_b64,
    negative_prompt: str = "",
    character_ref_url: str | None = None,
    location_ref_url: str | None = None,
    scene_id: str | None = None,
) -> tuple[dict, list[dict], str]:
    seed = _seed(scene_id)

    if character_ref_url and location_ref_url:
        return _build_character_location(
            scene_prompt=scene_prompt,
            visual_style=visual_style,
            negative_prompt=negative_prompt,
            character_b64=await load_image_b64(character_ref_url),
            location_b64=await load_image_b64(location_ref_url),
            seed=seed,
        )

    if character_ref_url:
        return _build_character(
            scene_prompt=scene_prompt,
            visual_style=visual_style,
            negative_prompt=negative_prompt,
            character_b64=await load_image_b64(character_ref_url),
            seed=seed,
        )

    if location_ref_url:
        return _build_location(
            scene_prompt=scene_prompt,
            visual_style=visual_style,
            negative_prompt=negative_prompt,
            location_b64=await load_image_b64(location_ref_url),
            seed=seed,
        )

    return _build_text(
        scene_prompt=scene_prompt,
        visual_style=visual_style,
        negative_prompt=negative_prompt,
        seed=seed,
    )
