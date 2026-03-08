import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook/runpod")
async def runpod_webhook(
    request: Request,
    x_runpod_signature_256: str = Header(default=""),
):
    body_bytes = await request.body()

    settings = request.app.state.settings
    if settings.WEBHOOK_SECRET:
        expected = hmac.new(
            settings.WEBHOOK_SECRET.encode(),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(f"sha256={expected}", x_runpod_signature_256):
            logger.warning("Invalid RunPod webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    body = await request.json()

    try:
        await request.app.state.webhook_handler.handle(body)
    except Exception as exc:
        logger.exception("Error handling RunPod webhook", exc_info=exc)
        return {"status": "error", "detail": str(exc)}

    return {"status": "ok"}
