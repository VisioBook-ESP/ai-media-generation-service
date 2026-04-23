import json

import pytest

from app.nats import publisher as pub_mod
from app.nats.publisher import NATSPublisher


class _Settings:
    NATS_URL = "nats://fake:4222"


class FakeJS:
    def __init__(self):
        self.published: list = []

    async def publish(self, subject, data):
        self.published.append((subject, data))


class FakeNC:
    def __init__(self):
        self.js = FakeJS()
        self.drained = False

    def jetstream(self):
        return self.js

    async def drain(self):
        self.drained = True


class TestPublisher:
    async def test_publish_before_connect_raises(self):
        p = NATSPublisher(_Settings())
        with pytest.raises(RuntimeError, match="not connected"):
            await p.publish("subj", {"x": 1})

    async def test_connect_publish_disconnect(self, monkeypatch):
        fake_nc = FakeNC()

        async def fake_connect(url):
            return fake_nc

        monkeypatch.setattr(pub_mod.nats, "connect", fake_connect)

        p = NATSPublisher(_Settings())
        await p.connect()
        await p.publish("visiobook.ai.test", {"hello": "world"})
        assert fake_nc.js.published == [
            ("visiobook.ai.test", json.dumps({"hello": "world"}).encode())
        ]

        await p.disconnect()
        assert fake_nc.drained is True

    async def test_disconnect_noop_if_not_connected(self):
        p = NATSPublisher(_Settings())
        await p.disconnect()
