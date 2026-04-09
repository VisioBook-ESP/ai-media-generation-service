from app.workflows.common import load_template, random_seed

_REQUIRED_NODES = {"3", "4", "10"}

_ANIMATION_QUALITY = (
    "cinemagraph, living painting, locked-off tripod shot, fixed frame, "
    "static background, subtle ambient motion only, "
    "particles floating, light flickering, gentle breeze effects, "
    "high quality, smooth animation"
)
_ANIMATION_NEGATIVE = (
    "camera movement, camera zoom, camera pan, camera shake, "
    "morphing, warping, deformation, "
    "worst quality, low quality, blurry, distorted"
)


def build(
    scene_prompt: str,
    visual_style: str = "",
) -> tuple[dict, list[dict]]:
    workflow = load_template("ltxv_i2v.json", _REQUIRED_NODES)

    positive = f"{scene_prompt}, {_ANIMATION_QUALITY}"
    if visual_style:
        positive = f"{positive}, {visual_style}"

    workflow["4"]["inputs"]["text"] = positive
    workflow["5"]["inputs"]["text"] = _ANIMATION_NEGATIVE
    workflow["10"]["inputs"]["noise_seed"] = random_seed()

    # Same image for first AND last frame → locks camera, prevents zoom drift
    return workflow, [{"name": "scene.png", "image": None}]
