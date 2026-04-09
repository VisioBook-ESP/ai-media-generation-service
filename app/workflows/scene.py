from app.workflows.common import load_template, random_seed

_TEXT_NODES = {"6", "31", "33"}
_LOCATION_NODES = {"6", "8", "9", "13"}
_CHARACTER_NODES = {"9", "12", "13", "15", "18"}
_CHARACTER_LOCATION_NODES = {"9", "10", "12", "13", "15", "18"}

_SCENE_BASE_QUALITY = "single illustration frame, cinematic composition, consistent storybook style"
_SCENE_NEGATIVE = "duplicate character, extra limbs, bad anatomy, cropped subject, cut off hands, cut off feet"


def _positive(scene_prompt: str, visual_style: str) -> str:
    return f"{scene_prompt}, {_SCENE_BASE_QUALITY}, {visual_style}"


def _negative(negative_prompt: str) -> str:
    return f"{_SCENE_NEGATIVE}, {negative_prompt}" if negative_prompt else _SCENE_NEGATIVE


def _build_text(scene_prompt: str, visual_style: str, negative_prompt: str) -> tuple[dict, list[dict], str]:
    workflow = load_template("flux_scene.json", _TEXT_NODES)
    workflow["6"]["inputs"]["text"] = _positive(scene_prompt, visual_style)
    workflow["33"]["inputs"]["text"] = _negative(negative_prompt)
    workflow["31"]["inputs"]["seed"] = random_seed()
    return workflow, [], "text"


def _build_location(
    scene_prompt: str,
    visual_style: str,
    negative_prompt: str,
    location_b64: str,
) -> tuple[dict, list[dict], str]:
    workflow = load_template("flux_scene_redux.json", _LOCATION_NODES)
    workflow["6"]["inputs"]["image"] = "reference.png"
    workflow["8"]["inputs"]["text"] = _positive(scene_prompt, visual_style)
    workflow["9"]["inputs"]["text"] = _negative(negative_prompt)
    workflow["13"]["inputs"]["seed"] = random_seed()
    return workflow, [{"name": "reference.png", "image": location_b64}], "location"


def _build_character(
    scene_prompt: str,
    visual_style: str,
    negative_prompt: str,
    character_b64: str,
) -> tuple[dict, list[dict], str]:
    """PuLID (face) + Redux (style/clothing) on character. No location ref."""
    workflow = load_template("flux_scene_pulid_redux.json", _CHARACTER_NODES)
    workflow["9"]["inputs"]["image"] = "character.png"
    workflow["12"]["inputs"]["text"] = _positive(scene_prompt, visual_style)
    workflow["13"]["inputs"]["text"] = _negative(negative_prompt)
    workflow["18"]["inputs"]["seed"] = random_seed()
    return workflow, [{"name": "character.png", "image": character_b64}], "character"


def _build_character_location(
    scene_prompt: str,
    visual_style: str,
    negative_prompt: str,
    character_b64: str,
    location_b64: str,
) -> tuple[dict, list[dict], str]:
    """PuLID (face) + Redux on character (strong) + Redux on location (light)."""
    workflow = load_template("flux_scene_pulid_redux.json", _CHARACTER_LOCATION_NODES)
    workflow["9"]["inputs"]["image"] = "character.png"
    workflow["10"]["inputs"]["image"] = "location.png"
    workflow["12"]["inputs"]["text"] = _positive(scene_prompt, visual_style)
    workflow["13"]["inputs"]["text"] = _negative(negative_prompt)
    workflow["18"]["inputs"]["seed"] = random_seed()
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
) -> tuple[dict, list[dict], str]:
    if character_ref_url and location_ref_url:
        return _build_character_location(
            scene_prompt=scene_prompt,
            visual_style=visual_style,
            negative_prompt=negative_prompt,
            character_b64=await load_image_b64(character_ref_url),
            location_b64=await load_image_b64(location_ref_url),
        )

    if character_ref_url:
        return _build_character(
            scene_prompt=scene_prompt,
            visual_style=visual_style,
            negative_prompt=negative_prompt,
            character_b64=await load_image_b64(character_ref_url),
        )

    if location_ref_url:
        return _build_location(
            scene_prompt=scene_prompt,
            visual_style=visual_style,
            negative_prompt=negative_prompt,
            location_b64=await load_image_b64(location_ref_url),
        )

    return _build_text(
        scene_prompt=scene_prompt,
        visual_style=visual_style,
        negative_prompt=negative_prompt,
    )
