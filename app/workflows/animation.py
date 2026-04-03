from app.workflows.common import load_template, random_seed

_REQUIRED_NODES = {"5", "6", "10"}

_ANIMATION_QUALITY = (
    "locked-off tripod shot, fixed frame, no camera movement, "
    "background remains completely still, "
    "subtle micro-movements only, subject animation only, "
    "high quality animation, animated illustration"
)
_ANIMATION_NEGATIVE = (
    "camera movement, camera pan, camera zoom, camera tilt, camera shake, "
    "camera rotation, camera drift, camera orbit, dolly, tracking shot, "
    "parallax, perspective shift, handheld, steadicam, "
    "Overexposure, blurred details, subtitles, worst quality, "
    "low quality, ugly, deformed, disfigured, fused fingers, three legs, upside down"
)


def build(
    scene_prompt: str,
    visual_style: str = "",
) -> tuple[dict, list[dict]]:
    workflow = load_template("wan21_i2v_480p.json", _REQUIRED_NODES)

    positive = f"{scene_prompt}, {_ANIMATION_QUALITY}"
    if visual_style:
        positive = f"{positive}, {visual_style}"

    workflow["6"]["inputs"]["text"] = positive
    workflow["7"]["inputs"]["text"] = _ANIMATION_NEGATIVE
    workflow["10"]["inputs"]["seed"] = random_seed()

    return workflow, [{"name": "scene.png", "image": None}]  # image filled by handler
