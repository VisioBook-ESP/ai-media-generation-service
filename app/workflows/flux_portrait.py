from app.workflows.common import deterministic_seed, load_template, random_seed

_REQUIRED_NODES = {"6", "27", "31", "33"}


def build(portrait_prompt: str, negative_prompt: str = "", character_id: str | None = None) -> dict:
    workflow = load_template("flux_portrait.json", _REQUIRED_NODES)
    workflow["6"]["inputs"]["text"] = portrait_prompt
    workflow["33"]["inputs"]["text"] = negative_prompt or "blurry, bad anatomy, extra limbs, multiple characters"
    workflow["31"]["inputs"]["seed"] = deterministic_seed(character_id) if character_id else random_seed()
    return workflow
