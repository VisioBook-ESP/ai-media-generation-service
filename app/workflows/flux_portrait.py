from app.workflows.common import load_template, random_seed

_REQUIRED_NODES = {"6", "27", "31", "33"}


def build(physical_description: str, visual_style: str, negative_prompt: str) -> dict:
    workflow = load_template("flux_portrait.json", _REQUIRED_NODES)
    workflow["6"]["inputs"]["text"] = (
        f"full body character reference of {physical_description}, "
        f"standing pose, entire body visible from head to toe, "
        f"clear outfit details, readable silhouette, neutral background, "
        f"well lit, front view, highly detailed, storybook character sheet, {visual_style}"
    )
    workflow["33"]["inputs"]["text"] = (
        f"cropped body, close-up portrait, upper body only, head cut off, feet cut off, "
        f"hands cut off, back view, profile view, side view, sitting pose, multiple characters, {negative_prompt}"
    )
    workflow["31"]["inputs"]["seed"] = random_seed()
    return workflow
