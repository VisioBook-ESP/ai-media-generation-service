import copy
import json
import random
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "workflow_templates"
_TEMPLATES: dict[str, dict] = {}


def load_template(name: str, required_nodes: set[str]) -> dict:
    if name not in _TEMPLATES:
        _TEMPLATES[name] = json.loads((_TEMPLATES_DIR / name).read_text())

    workflow = copy.deepcopy(_TEMPLATES[name])
    missing = sorted(required_nodes - workflow.keys())
    if missing:
        raise KeyError(f"Template '{name}' is missing nodes: {', '.join(missing)}")
    return workflow


def random_seed() -> int:
    return random.randint(0, 2**32 - 1)
