import base64

import httpx
import pytest

from app.clients import comfyui as comfyui_mod
from app.clients.comfyui import ComfyUIClient


def _resp(status: int, *, json=None, content=None, text=None) -> httpx.Response:
    """Build an httpx.Response with a bound request so raise_for_status() works."""
    req = httpx.Request("GET", "http://test/")
    kwargs: dict = {"request": req}
    if json is not None:
        kwargs["json"] = json
    if content is not None:
        kwargs["content"] = content
    if text is not None:
        kwargs["text"] = text
    return httpx.Response(status, **kwargs)


class FakeHttp:
    """Simulates ComfyUI's HTTP surface: /upload/image, /prompt, /history/*, /view."""

    def __init__(self):
        self.uploads: list = []
        self.prompts: list = []
        self.views: list = []
        self.history_queue: list = []  # dicts or httpx.Response
        self.prompt_response: httpx.Response | None = None
        self.view_response: bytes = b"BYTES"
        self.prompt_id: str = "prompt-1"
        self.post_override = None  # callable(url, **kw) -> Response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, **kwargs):
        if self.post_override is not None:
            return await self.post_override(url, **kwargs)
        if url == "/upload/image":
            self.uploads.append(kwargs)
            return _resp(200, json={})
        if url == "/prompt":
            self.prompts.append(kwargs)
            if self.prompt_response is not None:
                return self.prompt_response
            return _resp(200, json={"prompt_id": self.prompt_id})
        raise AssertionError(f"Unexpected POST {url}")

    async def get(self, url, **kwargs):
        if url.startswith("/history/"):
            if self.history_queue:
                item = self.history_queue.pop(0)
                if isinstance(item, httpx.Response):
                    return item
                return _resp(200, json=item)
            return _resp(404)
        if url == "/view":
            self.views.append(kwargs)
            return _resp(200, content=self.view_response)
        raise AssertionError(f"Unexpected GET {url}")


@pytest.fixture
def fake_http(monkeypatch):
    fake = FakeHttp()
    monkeypatch.setattr(comfyui_mod.httpx, "AsyncClient", lambda **kwargs: fake)

    async def fast_sleep(_):
        return None

    monkeypatch.setattr(comfyui_mod.asyncio, "sleep", fast_sleep)
    # Default to a single attempt so tests assert specific exceptions directly.
    # Tests that exercise the retry loop explicitly raise _MAX_RETRIES back to 2.
    monkeypatch.setattr(comfyui_mod, "_MAX_RETRIES", 1)
    return fake


def _completed(outputs: dict, prompt_id: str = "prompt-1") -> dict:
    return {prompt_id: {"status": {"completed": True}, "outputs": outputs}}


class TestRunWorkflowSuccess:
    async def test_happy_path_image(self, fake_http):
        fake_http.history_queue = [
            _completed({"9": {"images": [{"filename": "out.png"}]}})
        ]
        client = ComfyUIClient("http://comfy:8188/")
        result = await client.run_workflow(
            {"x": 1},
            images=[{"name": "ref.png", "image": base64.b64encode(b"IMG").decode()}],
        )
        assert result == b"BYTES"
        assert len(fake_http.uploads) == 1
        assert len(fake_http.prompts) == 1
        assert fake_http.views[0]["params"]["filename"] == "out.png"

    async def test_no_images_skips_upload(self, fake_http):
        fake_http.history_queue = [
            _completed({"9": {"images": [{"filename": "a.png"}]}})
        ]
        client = ComfyUIClient("http://comfy:8188")
        await client.run_workflow({"x": 1})
        assert fake_http.uploads == []

    async def test_404_then_success_polls_again(self, fake_http):
        fake_http.history_queue = [
            _resp(404),
            _completed({"9": {"images": [{"filename": "a.png"}]}}),
        ]
        client = ComfyUIClient("http://comfy:8188")
        assert await client.run_workflow({"x": 1}) == b"BYTES"

    async def test_success_via_status_str(self, fake_http):
        fake_http.history_queue = [
            {
                "prompt-1": {
                    "status": {"status_str": "success"},
                    "outputs": {"9": {"images": [{"filename": "a.png"}]}},
                }
            }
        ]
        client = ComfyUIClient("http://comfy:8188")
        assert await client.run_workflow({"x": 1}) == b"BYTES"

    async def test_video_picks_videos_array(self, fake_http):
        fake_http.history_queue = [
            _completed({"9": {"videos": [{"filename": "clip.mp4"}]}})
        ]
        client = ComfyUIClient("http://comfy:8188")
        result = await client.run_workflow({"x": 1}, output_type="video")
        assert result == b"BYTES"
        assert fake_http.views[0]["params"]["filename"] == "clip.mp4"

    async def test_gifs_array_fallback(self, fake_http):
        fake_http.history_queue = [_completed({"9": {"gifs": [{"filename": "a.gif"}]}})]
        client = ComfyUIClient("http://comfy:8188")
        assert await client.run_workflow({"x": 1}) == b"BYTES"
        assert fake_http.views[0]["params"]["filename"] == "a.gif"


class TestRunWorkflowErrors:
    async def test_history_error_status_raises(self, fake_http):
        fake_http.history_queue = [
            {
                "prompt-1": {
                    "status": {"status_str": "error: OOM"},
                    "outputs": {},
                }
            }
        ]
        client = ComfyUIClient("http://comfy:8188")
        with pytest.raises(RuntimeError, match="ComfyUI prompt failed"):
            await client.run_workflow({"x": 1})

    async def test_completed_but_no_outputs_raises(self, fake_http):
        fake_http.history_queue = [_completed({"9": {}})]
        client = ComfyUIClient("http://comfy:8188")
        with pytest.raises(ValueError, match="No output"):
            await client.run_workflow({"x": 1})

    async def test_prompt_non_200_raises(self, fake_http):
        fake_http.prompt_response = _resp(500, text="boom")
        client = ComfyUIClient("http://comfy:8188")
        with pytest.raises(httpx.HTTPStatusError):
            await client.run_workflow({"x": 1})

    async def test_timeout_raises(self, fake_http, monkeypatch):
        monkeypatch.setattr(comfyui_mod, "_POLL_TIMEOUT", 4.0)
        monkeypatch.setattr(comfyui_mod, "_POLL_INTERVAL", 2.0)
        # history_queue stays empty → always 404 → loop until timeout
        client = ComfyUIClient("http://comfy:8188")
        with pytest.raises(TimeoutError):
            await client.run_workflow({"x": 1})


class TestRetries:
    async def test_retries_then_succeeds(self, fake_http, monkeypatch):
        monkeypatch.setattr(comfyui_mod, "_MAX_RETRIES", 2)
        attempts = {"n": 0}

        async def flaky_post(url, **kwargs):
            if url == "/prompt":
                attempts["n"] += 1
                if attempts["n"] == 1:
                    raise httpx.ConnectError("boom")
            if url == "/upload/image":
                fake_http.uploads.append(kwargs)
                return _resp(200, json={})
            fake_http.prompts.append(kwargs)
            return _resp(200, json={"prompt_id": fake_http.prompt_id})

        fake_http.post_override = flaky_post
        fake_http.history_queue = [
            _completed({"9": {"images": [{"filename": "a.png"}]}})
        ]
        client = ComfyUIClient("http://comfy:8188")
        assert await client.run_workflow({"x": 1}) == b"BYTES"
        assert attempts["n"] == 2

    async def test_all_attempts_fail_raises_last(self, fake_http, monkeypatch):
        monkeypatch.setattr(comfyui_mod, "_MAX_RETRIES", 2)

        async def always_fail(url, **kwargs):
            raise httpx.ConnectError("down")

        fake_http.post_override = always_fail
        client = ComfyUIClient("http://comfy:8188")
        with pytest.raises(httpx.ConnectError, match="down"):
            await client.run_workflow({"x": 1})
