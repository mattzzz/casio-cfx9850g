"""TABLE mode tests."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.calculator.engine import CalculatorEngine
from app.calculator.modes.table import TableMode

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def tm():
    t = TableMode(CalculatorEngine())
    return t


# ── TableMode unit tests ──────────────────────────────────────────────────────

def test_generate_x_squared(tm):
    tm.set_function("X**2")
    tm.set_range(1, 5, 1)
    result = tm.generate()
    assert result["error"] is None
    rows = result["rows"]
    assert len(rows) == 5
    assert rows[0] == {"x": "1", "y": "1"}
    assert rows[1] == {"x": "2", "y": "4"}
    assert rows[4] == {"x": "5", "y": "25"}

def test_generate_linear(tm):
    tm.set_function("2*X + 1")
    tm.set_range(0, 3, 1)
    result = tm.generate()
    assert result["error"] is None
    rows = result["rows"]
    assert rows[0]["y"] == "1"
    assert rows[1]["y"] == "3"
    assert rows[2]["y"] == "5"
    assert rows[3]["y"] == "7"

def test_generate_float_step(tm):
    tm.set_function("X")
    tm.set_range(0, 1, 0.5)
    result = tm.generate()
    assert result["error"] is None
    assert len(result["rows"]) == 3   # 0, 0.5, 1

def test_generate_negative_step(tm):
    tm.set_function("X")
    tm.set_range(5, 1, -1)
    result = tm.generate()
    assert result["error"] is None
    rows = result["rows"]
    assert rows[0]["x"] == "5"
    assert rows[-1]["x"] == "1"

def test_generate_zero_step_error(tm):
    tm.set_function("X")
    tm.set_range(0, 5, 0)
    result = tm.generate()
    assert result["error"] is not None

def test_generate_no_function_error(tm):
    tm.set_range(1, 5, 1)
    result = tm.generate()
    assert result["error"] is not None

def test_generate_invalid_function_error(tm):
    tm.set_function(")(broken")
    tm.set_range(1, 5, 1)
    result = tm.generate()
    assert result["error"] is not None

def test_generate_trig_deg(tm):
    tm.set_function("sin(X)")
    tm.set_range(0, 90, 30)
    result = tm.generate()
    assert result["error"] is None
    rows = result["rows"]
    assert rows[0]["y"] == "0"       # sin(0) = 0
    assert rows[-1]["y"] == "1"      # sin(90°) = 1

def test_generate_trig_rad(tm):
    tm.engine.set_angle_mode("RAD")
    tm.set_function("sin(X)")
    tm.set_range(0, 1, 0.5)
    result = tm.generate()
    assert result["error"] is None
    # sin(0) = 0
    assert result["rows"][0]["y"] == "0"

def test_generate_constant_function(tm):
    tm.set_function("5")
    tm.set_range(1, 3, 1)
    result = tm.generate()
    for row in result["rows"]:
        assert row["y"] == "5"

def test_generate_division_by_zero(tm):
    tm.set_function("1/X")
    tm.set_range(0, 2, 1)
    result = tm.generate()
    assert result["error"] is None   # rows still generated
    assert result["rows"][0]["y"] == "Math ERROR"   # x=0 gives Math ERROR

def test_generate_log(tm):
    tm.set_function("log(X)")
    tm.set_range(1, 100, 9)
    result = tm.generate()
    assert result["error"] is None
    assert result["rows"][0]["y"] == "0"   # log(1) = 0

def test_generate_pi_constant(tm):
    tm.set_function("pi")
    tm.set_range(1, 2, 1)
    result = tm.generate()
    rows = result["rows"]
    assert "3.14" in rows[0]["y"]

def test_generate_single_row(tm):
    tm.set_function("X**2")
    tm.set_range(7, 7, 1)
    result = tm.generate()
    assert len(result["rows"]) == 1
    assert result["rows"][0] == {"x": "7", "y": "49"}

def test_generate_start_gt_end_positive_step(tm):
    tm.set_function("X")
    tm.set_range(5, 1, 1)   # invalid: start > end with positive step
    result = tm.generate()
    assert result["error"] is not None

def test_generate_ans_variable(tm):
    tm.engine.memory.set_ans(__import__('sympy').Integer(10))
    tm.set_function("X + Ans")
    tm.set_range(1, 3, 1)
    result = tm.generate()
    assert result["error"] is None
    assert result["rows"][0]["y"] == "11"   # 1 + 10

def test_generate_row_count(tm):
    tm.set_function("X")
    tm.set_range(1, 10, 1)
    result = tm.generate()
    assert len(result["rows"]) == 10

def test_generate_respects_max_rows(tm):
    tm.set_function("X")
    tm.set_range(1, 1000, 0.001)   # would be 999001 rows without cap
    result = tm.generate()
    assert len(result["rows"]) <= 500   # MAX_ROWS cap


# ── REST API tests ────────────────────────────────────────────────────────────

async def test_table_endpoint_basic(client):
    resp = await client.post("/api/table/generate", json={
        "function": "X**2", "start": 1, "end": 5, "step": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] is None
    assert len(data["rows"]) == 5

async def test_table_endpoint_rows_correct(client):
    resp = await client.post("/api/table/generate", json={
        "function": "X**2", "start": 1, "end": 3, "step": 1,
    })
    rows = resp.json()["rows"]
    assert rows[0] == {"x": "1", "y": "1"}
    assert rows[1] == {"x": "2", "y": "4"}
    assert rows[2] == {"x": "3", "y": "9"}

async def test_table_endpoint_float_step(client):
    resp = await client.post("/api/table/generate", json={
        "function": "X", "start": 0, "end": 1, "step": 0.5,
    })
    assert resp.status_code == 200
    assert len(resp.json()["rows"]) == 3

async def test_table_endpoint_trig(client):
    resp = await client.post("/api/table/generate", json={
        "function": "sin(X)", "start": 0, "end": 90, "step": 30,
        "angle_mode": "DEG",
    })
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert rows[0]["y"] == "0"
    assert rows[-1]["y"] == "1"

async def test_table_endpoint_zero_step_error(client):
    resp = await client.post("/api/table/generate", json={
        "function": "X", "start": 0, "end": 5, "step": 0,
    })
    assert resp.status_code == 200
    assert resp.json()["error"] is not None

async def test_table_endpoint_no_function(client):
    resp = await client.post("/api/table/generate", json={
        "function": "", "start": 1, "end": 5, "step": 1,
    })
    assert resp.status_code == 200
    assert resp.json()["error"] is not None

async def test_table_endpoint_angle_rad(client):
    resp = await client.post("/api/table/generate", json={
        "function": "sin(X)", "start": 0, "end": 1, "step": 1,
        "angle_mode": "RAD",
    })
    assert resp.status_code == 200
    assert resp.json()["rows"][0]["y"] == "0"

async def test_table_endpoint_negative_step(client):
    resp = await client.post("/api/table/generate", json={
        "function": "X", "start": 5, "end": 1, "step": -1,
    })
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert rows[0]["x"] == "5"
    assert rows[-1]["x"] == "1"
