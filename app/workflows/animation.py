from app.workflows.common import load_template, random_seed

_REQUIRED_NODES = {"3", "4", "10"}

_ANIMATION_QUALITY = (
    "cinematic, stable locked tripod camera, NO camera movement, "
    "subtle ambient animation only, "
    "particles floating gently in warm light, dust motes catching sunlight, "
    "soft fabric and hair swaying with gentle breeze, "
    "light flickering subtly, warm intimate lighting, "
    "perfectly still background, smooth gentle motion, "
    "high quality, refined and polished"
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
    workflow["10"]["inputs"]["noise_seed"] = random_seed()

    return workflow, [{"name": "scene.png", "image": None}]
