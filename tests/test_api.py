import pytest
import json
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient
from app.main import app


pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Health endpoint ──────────────────────────────────────────────────────────

async def test_health_status_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_health_returns_json(client):
    resp = await client.get("/health")
    data = resp.json()
    assert data["status"] == "ok"


async def test_health_model_field(client):
    resp = await client.get("/health")
    data = resp.json()
    assert data["model"] == "Casio CFX-9850G"


# ── Static file serving ──────────────────────────────────────────────────────

async def test_root_returns_html(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_root_contains_calculator(client):
    resp = await client.get("/")
    assert "calculator" in resp.text.lower()


async def test_static_css_calculator(client):
    resp = await client.get("/static/css/calculator.css")
    assert resp.status_code == 200


async def test_static_css_screen(client):
    resp = await client.get("/static/css/screen.css")
    assert resp.status_code == 200


async def test_static_js_app(client):
    resp = await client.get("/static/js/app.js")
    assert resp.status_code == 200


async def test_static_js_display(client):
    resp = await client.get("/static/js/display.js")
    assert resp.status_code == 200


async def test_static_js_keyboard(client):
    resp = await client.get("/static/js/keyboard.js")
    assert resp.status_code == 200


async def test_static_js_modes(client):
    resp = await client.get("/static/js/modes.js")
    assert resp.status_code == 200


async def test_static_js_graph(client):
    resp = await client.get("/static/js/graph.js")
    assert resp.status_code == 200


async def test_static_404(client):
    resp = await client.get("/static/nonexistent.file")
    assert resp.status_code == 404


# ── WebSocket — Phase 2 JSON protocol ───────────────────────────────────────
# Starlette's TestClient is used for WebSocket tests (synchronous but correct)

def _ws_key(ws, key):
    """Send a key event and return parsed response."""
    ws.send_text(json.dumps({"type": "key", "key": key}))
    return json.loads(ws.receive_text())


def test_websocket_echo_text():
    """Invalid JSON returns an error response (no longer plain echo)."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/calculator") as ws:
            ws.send_text("hello")
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "error"


def test_websocket_echo_json():
    """Key event returns a display state dict."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/calculator") as ws:
            resp = _ws_key(ws, "5")
            assert resp["type"] == "display"
            assert "5" in resp["expression"]


def test_websocket_echo_multiple():
    """Multiple key events accumulate in expression."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/calculator") as ws:
            _ws_key(ws, "1")
            _ws_key(ws, "PLUS")
            resp = _ws_key(ws, "2")
            assert "1" in resp["expression"]
            assert "2" in resp["expression"]


def test_websocket_connects():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/calculator") as ws:
            assert ws is not None
