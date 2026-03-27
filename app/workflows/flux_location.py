from app.workflows.common import load_template, random_seed

_REQUIRED_NODES = {"6", "27", "31", "33"}


def build(location_description: str, visual_style: str, negative_prompt: str) -> dict:
    workflow = load_template("flux_location.json", _REQUIRED_NODES)
    workflow["6"]["inputs"]["text"] = (
        f"{location_description}, "
        f"environment concept art, establishing shot, wide angle view, full environment visible, "
        f"strong sense of place, no characters, no people, highly detailed background, {visual_style}"
    )
    workflow["33"]["inputs"]["text"] = (
        f"people, characters, portrait framing, close-up subject, cropped environment, {negative_prompt}"
    )
    workflow["31"]["inputs"]["seed"] = random_seed()
    return workflow
