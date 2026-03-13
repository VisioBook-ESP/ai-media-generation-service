import copy
import json
import random
from pathlib import Path

_TEMPLATE_PATH = Path("workflow_templates/wan21_i2v.json")
_TEMPLATE: dict | None = None


def _get_template() -> dict:
    global _TEMPLATE
    if _TEMPLATE is None:
        _TEMPLATE = json.loads(_TEMPLATE_PATH.read_text())
    return _TEMPLATE


def build(
    video_prompt: str,
    image_name: str = "scene_image.png",
    width: int = 832,
    height: int = 480,
    length: int = 81,
) -> dict:
    workflow = copy.deepcopy(_get_template())
    workflow["4"]["inputs"]["image"] = image_name
    workflow["5"]["inputs"]["text"] = video_prompt
    workflow["7"]["inputs"]["width"] = width
    workflow["7"]["inputs"]["height"] = height
    workflow["7"]["inputs"]["length"] = length
    workflow["8"]["inputs"]["seed"] = random.randint(0, 2**32 - 1)
    return workflow
