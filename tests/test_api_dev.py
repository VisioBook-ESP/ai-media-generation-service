from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import dev as dev_mod
from app.api.dev import router as dev_router


class FakePublisher:
    def __init__(self):
        self.published: list = []

    async def publish(self, subject, data):
        self.published.append((subject, data))


def _make_app(publisher: FakePublisher) -> FastAPI:
    app = FastAPI()
    app.include_router(dev_router)
    app.state.publisher = publisher
    return app


class TestEventsEndpoint:
    def test_empty_when_no_events(self):
        dev_mod._events.clear()
        client = TestClient(_make_app(FakePublisher()))
        r = client.get("/dev/events")
        assert r.status_code == 200
        assert r.json() == []

    def test_filters_after_id(self):
        dev_mod._events.clear()
        dev_mod._events.append({"id": 1, "ts": 0, "subject": "a", "data": {}})
        dev_mod._events.append({"id": 2, "ts": 1, "subject": "b", "data": {}})
        client = TestClient(_make_app(FakePublisher()))
        r = client.get("/dev/events?after=1")
        assert [e["id"] for e in r.json()] == [2]


class TestTriggerGenerate:
    def test_publishes_to_nats(self):
        pub = FakePublisher()
        client = TestClient(_make_app(pub))
        body = {"projectId": "p1", "executionId": "e1"}
        r = client.post("/dev/generate", json=body)
        assert r.status_code == 200
        assert r.json() == {"status": "published", "projectId": "p1"}
        assert pub.published == [("visiobook.media.generate", body)]


class TestDevUi:
    def test_returns_html(self):
        client = TestClient(_make_app(FakePublisher()))
        r = client.get("/dev/")
        assert r.status_code == 200
        assert "Visiobook Media" in r.text
        assert r.headers["content-type"].startswith("text/html")
