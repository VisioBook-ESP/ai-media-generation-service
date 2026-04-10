from app.workflows.common import deterministic_seed, load_template, random_seed

_REQUIRED_NODES = {"6", "27", "31", "33"}


def build(location_prompt: str, negative_prompt: str = "", location_id: str | None = None) -> dict:
    workflow = load_template("flux_location.json", _REQUIRED_NODES)
    workflow["6"]["inputs"]["text"] = location_prompt
    workflow["33"]["inputs"]["text"] = negative_prompt or "people, characters, text, modern objects"
    workflow["31"]["inputs"]["seed"] = deterministic_seed(location_id) if location_id else random_seed()
    return workflow
