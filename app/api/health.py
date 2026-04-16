import logging

import httpx
from fastapi import APIRouter, Request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health(request: Request):
    checks = {"service": "ok"}

    # NATS
    try:
        consumer = getattr(request.app.state, "nats_consumer", None)
        if consumer and consumer._nc and consumer._nc.is_connected:
            checks["nats"] = "ok"
        else:
            checks["nats"] = "disconnected"
    except Exception:
        checks["nats"] = "error"

    # ComfyUI
    try:
        comfyui = getattr(request.app.state, "comfyui", None)
        if comfyui:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{comfyui._base_url}/system_stats")
                checks["comfyui"] = "ok" if resp.status_code == 200 else "unavailable"
        else:
            checks["comfyui"] = "not_configured"
    except Exception:
        checks["comfyui"] = "unreachable"

    healthy = all(v == "ok" for v in checks.values())
    return {"status": "ok" if healthy else "degraded", "checks": checks}
