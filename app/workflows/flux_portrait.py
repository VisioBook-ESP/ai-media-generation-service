import copy
import json
import random
from pathlib import Path

_TEMPLATE_PATH = Path("workflow_templates/flux_portrait.json")
_TEMPLATE: dict | None = None


def _get_template() -> dict:
    global _TEMPLATE
    if _TEMPLATE is None:
        _TEMPLATE = json.loads(_TEMPLATE_PATH.read_text())
    return _TEMPLATE


def build(physical_description: str, visual_style: str, negative_prompt: str) -> dict:
    workflow = copy.deepcopy(_get_template())
    workflow["6"]["inputs"]["text"] = (
        f"portrait of {physical_description}, "
        f"face clearly visible, looking at camera, neutral background, "
        f"well lit, upper body shot, detailed face, high quality, {visual_style}"
    )
    workflow["33"]["inputs"]["text"] = f"back view, profile view, side view, {negative_prompt}"
    workflow["31"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
    return workflow
