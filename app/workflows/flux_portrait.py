from app.workflows.common import deterministic_seed, load_template, random_seed

_REQUIRED_NODES = {"6", "10", "33"}


def build(
    portrait_prompt: str, negative_prompt: str = "", character_id: str | None = None
) -> dict:
    workflow = load_template("flux_portrait.json", _REQUIRED_NODES)
    workflow["6"]["inputs"]["text"] = portrait_prompt
    workflow["33"]["inputs"]["text"] = (
        "cropped body, close-up portrait, upper body only, head cut off, feet cut off, "
        "hands cut off, back view, profile view, side view, sitting pose, multiple characters"
        + (f", {negative_prompt}" if negative_prompt else "")
    )
    workflow["10"]["inputs"]["noise_seed"] = (
        deterministic_seed(character_id) if character_id else random_seed()
    )
    return workflow
