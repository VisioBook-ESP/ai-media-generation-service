from app.workflows.common import deterministic_seed, load_template, random_seed

_REQUIRED_NODES = {"3", "4", "6", "10", "11", "13"}
_ANIMATION_FPS = 24
_DEFAULT_DURATION_SEC = 5.0
_MIN_DURATION_SEC = 2.0
_MAX_DURATION_SEC = 6.0

_ANIMATION_QUALITY = (
    "cinematic, stable composition, preserve the original framing and scene layout, "
    "preserve character identity and wardrobe, preserve environment structure, "
    "very subtle camera drift at most, no zoom, no whip pan, "
    "gentle natural motion only, soft breathing, blinking, hair and fabric swaying lightly, "
    "ambient particles and light flicker, smooth temporal consistency, "
    "high quality, refined and polished"
)


def _clamp_duration(duration_sec: float | None) -> float:
    if duration_sec is None:
        return _DEFAULT_DURATION_SEC
    return max(_MIN_DURATION_SEC, min(_MAX_DURATION_SEC, float(duration_sec)))


def _ltx_num_frames(duration_sec: float, fps: int) -> int:
    target_frames = max(9, int(round(duration_sec * fps)))
    # LTX-Video works best with frame counts shaped as 8n + 1.
    return ((target_frames - 1 + 7) // 8) * 8 + 1


def build(
    scene_prompt: str,
    visual_style: str = "",
    scene_id: str | None = None,
    duration_sec: float | None = None,
) -> tuple[dict, list[dict]]:
    workflow = load_template("ltxv_i2v.json", _REQUIRED_NODES)
    duration_sec = _clamp_duration(duration_sec)
    num_frames = _ltx_num_frames(duration_sec, _ANIMATION_FPS)

    positive = f"{scene_prompt}, {_ANIMATION_QUALITY}"
    if visual_style:
        positive = f"{positive}, {visual_style}"

    workflow["4"]["inputs"]["text"] = positive
    workflow["6"]["inputs"]["frame_rate"] = _ANIMATION_FPS
    workflow["10"]["inputs"]["noise_seed"] = deterministic_seed(scene_id, "animation") if scene_id else random_seed()
    workflow["11"]["inputs"]["num_frames"] = num_frames
    workflow["13"]["inputs"]["fps"] = _ANIMATION_FPS

    return workflow, [{"name": "scene.png", "image": None}]
