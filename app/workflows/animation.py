from app.workflows.common import deterministic_seed, load_template, random_seed

_REQUIRED_NODES = {
    "75",
    "269",
    "267:237",
    "267:216",
    "267:266",
    "267:247",
    "267:225",
    "267:260",
}

_ANIMATION_FPS = 25
_DEFAULT_DURATION_SEC = 4.0
_MIN_DURATION_SEC = 2.0
_MAX_DURATION_SEC = 6.0


def _clamp_duration(duration_sec: float | None) -> float:
    if duration_sec is None:
        return _DEFAULT_DURATION_SEC
    return max(_MIN_DURATION_SEC, min(_MAX_DURATION_SEC, float(duration_sec)))


def _ltx_num_frames(duration_sec: float, fps: int) -> int:
    target_frames = max(9, int(round(duration_sec * fps)))
    # LTX-Video 2.3 works best with frame counts shaped as 8n + 1.
    return ((target_frames - 1 + 7) // 8) * 8 + 1


def build(
    scene_prompt: str,
    visual_style: str = "",
    scene_id: str | None = None,
    duration_sec: float | None = None,
) -> tuple[dict, list[dict]]:
    workflow = load_template("ltxv_23_i2v.json", _REQUIRED_NODES)

    duration_sec = _clamp_duration(duration_sec)
    num_frames = _ltx_num_frames(duration_sec, _ANIMATION_FPS)

    # Prompt (enhanced by Gemma via TextGenerateLTX2Prompt)
    prompt = scene_prompt
    if visual_style:
        prompt = f"{prompt}, {visual_style}"
    workflow["267:266"]["inputs"]["value"] = prompt

    # Negative prompt
    workflow["267:247"]["inputs"]["text"] = (
        "low quality, worst quality, blurry, distorted, ugly, "
        "static image, freeze frame, no motion"
    )

    # Frame count and FPS
    workflow["267:225"]["inputs"]["value"] = num_frames
    workflow["267:260"]["inputs"]["value"] = _ANIMATION_FPS

    # Seeds
    seed = deterministic_seed(scene_id, "animation") if scene_id else random_seed()
    workflow["267:237"]["inputs"]["noise_seed"] = seed  # low-res pass
    workflow["267:216"]["inputs"]["noise_seed"] = seed + 1  # high-res pass

    return workflow, [{"name": "scene.png", "image": None}]
