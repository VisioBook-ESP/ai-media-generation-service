from app.config import Settings
from app import main


def test_settings_defaults_load():
    s = Settings(_env_file=None)
    assert s.PORT == 8087
    assert s.ENV in ("development", "production")
    assert s.NATS_STREAM == "visiobook"


def test_app_exposes_health_route():
    routes = {r.path for r in main.app.routes}
    assert "/health" in routes
    assert main.app.title == "ai-media-generation-service"
