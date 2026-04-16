from app.workflows.common import deterministic_seed, load_template, random_seed

_REQUIRED_NODES = {"6", "10", "33"}


def build(location_prompt: str, negative_prompt: str = "", location_id: str | None = None) -> dict:
    workflow = load_template("flux_location.json", _REQUIRED_NODES)
    workflow["6"]["inputs"]["text"] = location_prompt
    workflow["33"]["inputs"]["text"] = (
        f"people, characters, portrait framing, close-up subject, cropped environment"
        + (f", {negative_prompt}" if negative_prompt else "")
    )
    workflow["10"]["inputs"]["noise_seed"] = deterministic_seed(location_id) if location_id else random_seed()
    return workflow
