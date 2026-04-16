import re


def _slugify(name: str) -> str:
    """Convert a display name to a filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_") or "unnamed"


def character_ref(user_id: str, project_id: str, character_name: str) -> str:
    return f"{user_id}/{project_id}/characters/{_slugify(character_name)}/reference.png"


def location_ref(user_id: str, project_id: str, location_id: str) -> str:
    return f"{user_id}/{project_id}/locations/{location_id}/reference.png"


def scene_image(user_id: str, project_id: str, scene_id: str) -> str:
    return f"{user_id}/{project_id}/scenes/{scene_id}/image.png"


def animated_scene(user_id: str, project_id: str, scene_id: str) -> str:
    return f"{user_id}/{project_id}/animated_scenes/{scene_id}/animation.mp4"
