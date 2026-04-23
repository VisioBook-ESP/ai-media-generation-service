import asyncio
import json

import nats
import pytest

from app.nats import consumer as consumer_mod
from app.nats.consumer import NATSConsumer, _run_with_heartbeat


class _Settings:
    NATS_URL = "nats://fake:4222"
    NATS_STREAM = "test-stream"


class FakeMsg:
    def __init__(self, data: bytes):
        self.data = data
        self.acks = 0
        self.naks: list = []
        self.in_progress_calls = 0

    async def ack(self):
        self.acks += 1

    async def nak(self, delay=0):
        self.naks.append(delay)

    async def in_progress(self):
        self.in_progress_calls += 1


class FakeHandler:
    def __init__(self, raise_exc: Exception | None = None):
        self.calls: list = []
        self.raise_exc = raise_exc

    async def handle(self, data):
        self.calls.append(data)
        if self.raise_exc:
            raise self.raise_exc


class _StreamInfo:
    def __init__(self, subjects):
        class _Config:
            pass

        self.config = _Config()
        self.config.subjects = subjects


class FakeJS:
    def __init__(self, *, stream_not_found: bool = False, existing_subjects=None):
        self.stream_not_found = stream_not_found
        self.existing_subjects = existing_subjects or []
        self.added_streams: list = []
        self.updated_streams: list = []
        self.deleted_consumers: list = []
        self.subscribed: list = []

    async def stream_info(self, name):
        if self.stream_not_found:
            raise nats.js.errors.NotFoundError()
        return _StreamInfo(self.existing_subjects.copy())

    async def add_stream(self, **kwargs):
        self.added_streams.append(kwargs)

    async def update_stream(self, *, name, subjects):
        self.updated_streams.append((name, subjects))

    async def delete_consumer(self, stream, durable):
        self.deleted_consumers.append((stream, durable))

    async def subscribe(self, subject, **kwargs):
        self.subscribed.append({"subject": subject, **kwargs})


class FakeNC:
    def __init__(self, js):
        self._js = js

    def jetstream(self):
        return self._js

    async def drain(self):
        pass


class TestOnGenerate:
    async def test_acks_on_success(self):
        handler = FakeHandler()
        c = NATSConsumer(_Settings(), handler)
        msg = FakeMsg(json.dumps({"projectId": "p", "executionId": "e"}).encode())
        await c._on_generate(msg)
        assert handler.calls == [{"projectId": "p", "executionId": "e"}]
        assert msg.acks == 1
        assert msg.naks == []

    async def test_naks_on_handler_exception(self):
        handler = FakeHandler(raise_exc=RuntimeError("boom"))
        c = NATSConsumer(_Settings(), handler)
        msg = FakeMsg(json.dumps({"x": 1}).encode())
        await c._on_generate(msg)
        assert msg.acks == 0
        assert msg.naks == [5]

    async def test_naks_on_bad_json(self):
        handler = FakeHandler()
        c = NATSConsumer(_Settings(), handler)
        msg = FakeMsg(b"not-json")
        await c._on_generate(msg)
        assert msg.acks == 0
        assert msg.naks == [5]


class TestHeartbeat:
    async def test_returns_handler_result(self):
        msg = FakeMsg(b"{}")

        async def work():
            await asyncio.sleep(0)
            return "done"

        result = await _run_with_heartbeat(msg, work())
        assert result == "done"
        assert msg.in_progress_calls >= 1

    async def test_propagates_exception_and_cancels_task(self):
        msg = FakeMsg(b"{}")

        async def work():
            await asyncio.sleep(0)
            raise ValueError("nope")

        with pytest.raises(ValueError, match="nope"):
            await _run_with_heartbeat(msg, work())


class TestStart:
    async def test_creates_stream_when_not_found(self, monkeypatch):
        js = FakeJS(stream_not_found=True)
        nc = FakeNC(js)

        async def fake_connect(url):
            return nc

        monkeypatch.setattr(consumer_mod.nats, "connect", fake_connect)
        c = NATSConsumer(_Settings(), FakeHandler())
        await c.start()

        assert len(js.added_streams) == 1
        assert js.added_streams[0]["name"] == "test-stream"
        assert "visiobook.media.>" in js.added_streams[0]["subjects"]
        assert js.subscribed[0]["subject"] == "visiobook.media.generate"

    async def test_adds_missing_subject_to_existing_stream(self, monkeypatch):
        js = FakeJS(existing_subjects=["visiobook.ai.>"])
        nc = FakeNC(js)

        async def fake_connect(url):
            return nc

        monkeypatch.setattr(consumer_mod.nats, "connect", fake_connect)
        c = NATSConsumer(_Settings(), FakeHandler())
        await c.start()

        assert js.added_streams == []
        assert js.updated_streams == [
            ("test-stream", ["visiobook.ai.>", "visiobook.media.>"])
        ]

    async def test_skips_update_when_subject_present(self, monkeypatch):
        js = FakeJS(existing_subjects=["visiobook.media.>", "visiobook.ai.>"])
        nc = FakeNC(js)

        async def fake_connect(url):
            return nc

        monkeypatch.setattr(consumer_mod.nats, "connect", fake_connect)
        c = NATSConsumer(_Settings(), FakeHandler())
        await c.start()

        assert js.updated_streams == []
        assert js.subscribed[0]["durable"] == "ai-media-gen-pipeline"


class TestStop:
    async def test_stop_drains_when_connected(self, monkeypatch):
        js = FakeJS(existing_subjects=["visiobook.media.>"])
        nc = FakeNC(js)

        async def fake_connect(url):
            return nc

        monkeypatch.setattr(consumer_mod.nats, "connect", fake_connect)
        c = NATSConsumer(_Settings(), FakeHandler())
        await c.start()
        await c.stop()  # should not raise

    async def test_stop_noop_when_not_started(self):
        c = NATSConsumer(_Settings(), FakeHandler())
        await c.stop()
