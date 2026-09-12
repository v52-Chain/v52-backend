"""Configuration contracts that affect the deployed PWA."""

from fastapi.testclient import TestClient

from app.config import Settings


def test_cors_origins_are_explicit_and_normalized() -> None:
    settings = Settings(
        V52_CORS_ORIGINS=(
            "https://vector52.vercel.app/, "
            "https://preview.vector52.example"
        )
    )

    assert settings.cors_origins == [
        "https://vector52.vercel.app",
        "https://preview.vector52.example",
    ]


def test_cors_origins_default_to_empty() -> None:
    assert Settings(V52_CORS_ORIGINS="").cors_origins == []


def test_configured_cors_origin_is_returned_on_preflight(monkeypatch) -> None:
    from app.config import invalidate_settings
    from app.main import create_app

    origin = "https://vector52.vercel.app"
    monkeypatch.setenv("V52_CORS_ORIGINS", origin)
    invalidate_settings()

    with TestClient(create_app()) as client:
        response = client.options(
            "/healthz",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
