"""GRAPH mode tests."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.calculator.engine import CalculatorEngine
from app.calculator.modes.graph import GraphMode, DEFAULT_WINDOW

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def gm():
    return GraphMode(CalculatorEngine())


# ── GraphMode unit tests ──────────────────────────────────────────────────────

def test_default_window(gm):
    assert gm.window["xmin"] == DEFAULT_WINDOW["xmin"]
    assert gm.window["xmax"] == DEFAULT_WINDOW["xmax"]

def test_set_function(gm):
    gm.set_function(0, "sin(X)")
    assert gm.functions[0] == "sin(X)"

def test_set_function_index_bounds(gm):
    gm.set_function(3, "X")   # out of range — silently ignored
    assert gm.functions == ["", "", ""]

def test_set_window(gm):
    gm.set_window(xmin=-10, xmax=10)
    assert gm.window["xmin"] == -10
    assert gm.window["xmax"] == 10

def test_reset_window(gm):
    gm.set_window(xmin=-100, xmax=100)
    gm.reset_window()
    assert gm.window["xmin"] == DEFAULT_WINDOW["xmin"]

def test_zoom_in(gm):
    old_range = gm.window["xmax"] - gm.window["xmin"]
    gm.zoom_in()
    new_range = gm.window["xmax"] - gm.window["xmin"]
    assert new_range < old_range

def test_zoom_out(gm):
    old_range = gm.window["xmax"] - gm.window["xmin"]
    gm.zoom_out()
    new_range = gm.window["xmax"] - gm.window["xmin"]
    assert new_range > old_range

def test_zoom_standard(gm):
    gm.zoom_standard()
    assert gm.window["xmin"] == -10
    assert gm.window["xmax"] == 10

def test_zoom_trig(gm):
    gm.zoom_trig()
    assert gm.window["xmin"] == -360
    assert gm.window["xmax"] == 360

def test_plot_returns_svg(gm):
    gm.set_function(0, "sin(X)")
    svg = gm.plot()
    assert "<svg" in svg
    assert "</svg>" in svg

def test_plot_empty_functions(gm):
    svg = gm.plot()
    assert "<svg" in svg   # still renders (with "No functions" text)

def test_plot_multiple_functions(gm):
    gm.set_function(0, "sin(X)")
    gm.set_function(1, "cos(X)")
    gm.set_function(2, "X**2/10")
    svg = gm.plot()
    assert "<svg" in svg

def test_plot_invalid_function(gm):
    gm.set_function(0, "1/0")   # should not crash; renders empty/nan line
    svg = gm.plot()
    assert "<svg" in svg

def test_plot_trig_deg_mode(gm):
    gm.engine.set_angle_mode("DEG")
    gm.set_function(0, "sin(X)")
    svg = gm.plot()
    assert "<svg" in svg

def test_plot_trig_rad_mode(gm):
    gm.engine.set_angle_mode("RAD")
    gm.set_function(0, "sin(X)")
    gm.zoom_trig()
    gm.window.update({"xmin": -6.3, "xmax": 6.3})
    svg = gm.plot()
    assert "<svg" in svg

def test_eval_function_sin(gm):
    import numpy as np
    xs = np.array([0.0, 90.0])
    ys = gm._eval_function("sin(X)", xs)
    assert ys is not None
    assert abs(ys[1] - 1.0) < 1e-6   # sin(90°) = 1 in DEG mode

def test_eval_function_invalid(gm):
    import numpy as np
    ys = gm._eval_function(")(invalid", np.array([1.0]))
    assert ys is None


# ── REST API tests ────────────────────────────────────────────────────────────

async def test_graph_plot_endpoint_returns_svg(client):
    resp = await client.post("/api/graph/plot", json={
        "functions": ["sin(X)", "", ""],
        "window": {"xmin": -6.3, "xmax": 6.3, "ymin": -1.5, "ymax": 1.5,
                   "xscl": 1, "yscl": 0.5},
        "angle_mode": "DEG",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "svg" in data
    assert "<svg" in data["svg"]

async def test_graph_plot_returns_window(client):
    resp = await client.post("/api/graph/plot", json={
        "functions": ["X**2"],
    })
    assert resp.status_code == 200
    assert "window" in resp.json()

async def test_graph_plot_empty_functions(client):
    resp = await client.post("/api/graph/plot", json={"functions": ["", "", ""]})
    assert resp.status_code == 200
    assert "<svg" in resp.json()["svg"]

async def test_graph_plot_multiple(client):
    resp = await client.post("/api/graph/plot", json={
        "functions": ["sin(X)", "cos(X)", "tan(X)"],
        "angle_mode": "DEG",
    })
    assert resp.status_code == 200
    assert "<svg" in resp.json()["svg"]

async def test_graph_plot_rad_mode(client):
    resp = await client.post("/api/graph/plot", json={
        "functions": ["sin(X)"],
        "window": {"xmin": -6.3, "xmax": 6.3, "ymin": -1.5, "ymax": 1.5,
                   "xscl": 1, "yscl": 0.5},
        "angle_mode": "RAD",
    })
    assert resp.status_code == 200

async def test_graph_plot_polynomial(client):
    resp = await client.post("/api/graph/plot", json={
        "functions": ["X**3 - 3*X"],
    })
    assert resp.status_code == 200

async def test_graph_plot_log(client):
    resp = await client.post("/api/graph/plot", json={
        "functions": ["log(X)"],
        "window": {"xmin": 0.1, "xmax": 10, "ymin": -1, "ymax": 2,
                   "xscl": 1, "yscl": 0.5},
    })
    assert resp.status_code == 200

async def test_graph_svg_is_inline(client):
    resp = await client.post("/api/graph/plot", json={"functions": ["X"]})
    svg = resp.json()["svg"]
    assert not svg.startswith("/")   # not a file path — must be inline

async def test_graph_custom_window(client):
    resp = await client.post("/api/graph/plot", json={
        "functions": ["X**2"],
        "window": {"xmin": -5, "xmax": 5, "ymin": 0, "ymax": 25,
                   "xscl": 1, "yscl": 5},
    })
    assert resp.status_code == 200
    assert resp.json()["window"]["xmin"] == -5

async def test_graph_invalid_function_no_crash(client):
    resp = await client.post("/api/graph/plot", json={
        "functions": [")(broken"],
    })
    assert resp.status_code == 200   # should not 500
