import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.health import router as health_router


class FakeNats:
    """Mimics NATSConsumer's exposed attributes used by /health."""

    def __init__(self, connected: bool):
        class _NC:
            is_connected = connected

        self._nc = _NC()


class FakeComfyUI:
    def __init__(self, base_url: str = "http://comfy:8188"):
        self._base_url = base_url


def _make_app(*, nats_consumer=None, comfyui=None) -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    app.state.nats_consumer = nats_consumer
    app.state.comfyui = comfyui
    return app


async def _get_health(app: FastAPI) -> dict:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    return r.json()


@pytest.fixture
def patch_comfy_httpx(monkeypatch):
    """Replace httpx.AsyncClient (as imported by app.api.health) with a fake.

    Returns a setter `set_response(response=None, raise_exc=None)` that the test
    can call to control the next /system_stats response.
    """
    state: dict = {"response": httpx.Response(200, json={}), "raise_exc": None}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            if state["raise_exc"]:
                raise state["raise_exc"]
            return state["response"]

    monkeypatch.setattr("app.api.health.httpx.AsyncClient", FakeClient)

    def configure(*, response=None, raise_exc=None):
        if response is not None:
            state["response"] = response
        if raise_exc is not None:
            state["raise_exc"] = raise_exc

    return configure


class TestHealthDegraded:
    async def test_no_state_returns_degraded(self):
        body = await _get_health(_make_app())
        assert body["status"] == "degraded"
        assert body["checks"] == {
            "service": "ok",
            "nats": "disconnected",
            "comfyui": "not_configured",
        }

    async def test_nats_disconnected(self):
        body = await _get_health(_make_app(nats_consumer=FakeNats(connected=False)))
        assert body["checks"]["nats"] == "disconnected"
        assert body["status"] == "degraded"


class TestHealthFull:
    async def test_all_ok(self, patch_comfy_httpx):
        patch_comfy_httpx(response=httpx.Response(200, json={}))
        body = await _get_health(
            _make_app(
                nats_consumer=FakeNats(connected=True),
                comfyui=FakeComfyUI("http://comfy:8188"),
            )
        )
        assert body == {
            "status": "ok",
            "checks": {"service": "ok", "nats": "ok", "comfyui": "ok"},
        }

    async def test_comfyui_500_marks_unavailable(self, patch_comfy_httpx):
        patch_comfy_httpx(response=httpx.Response(500))
        body = await _get_health(
            _make_app(
                nats_consumer=FakeNats(connected=True),
                comfyui=FakeComfyUI("http://comfy:8188"),
            )
        )
        assert body["checks"]["comfyui"] == "unavailable"
        assert body["status"] == "degraded"

    async def test_comfyui_network_error_marks_unreachable(self, patch_comfy_httpx):
        patch_comfy_httpx(raise_exc=httpx.ConnectError("boom"))
        body = await _get_health(
            _make_app(
                nats_consumer=FakeNats(connected=True),
                comfyui=FakeComfyUI("http://comfy:8188"),
            )
        )
        assert body["checks"]["comfyui"] == "unreachable"
        assert body["status"] == "degraded"
