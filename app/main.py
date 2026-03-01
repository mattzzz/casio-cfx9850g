from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import os

from app.calculator.engine import CalculatorEngine
from app.calculator.modes.comp import CompMode
from app.calculator.modes.graph import GraphMode
from app.calculator.modes.table import TableMode

app = FastAPI(title="Casio CFX-9850G Emulator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/health")
async def health():
    return {"status": "ok", "model": "Casio CFX-9850G"}


@app.get("/", response_class=HTMLResponse)
async def root():
    with open(os.path.join(static_dir, "index.html")) as f:
        return f.read()


# ── REST convenience endpoint for COMP evaluation ────────────────────────────

@app.post("/api/comp/evaluate")
async def comp_evaluate(body: dict):
    """Evaluate a COMP expression directly.
    Body: {"expression": "...", "angle_mode": "DEG"}
    """
    engine = CalculatorEngine()
    angle = body.get("angle_mode", "DEG")
    engine.set_angle_mode(angle)
    result = engine.evaluate(body.get("expression", ""))
    return {"result": result, "angle_mode": angle}


# ── Graph endpoint ───────────────────────────────────────────────────────────

@app.post("/api/graph/plot")
async def graph_plot(body: dict):
    """Plot Y= functions and return inline SVG.

    Body: {
        "functions": ["sin(X)", "", ""],   # Y1..Y3
        "window": {"xmin": -6.3, "xmax": 6.3, "ymin": -3.1, "ymax": 3.1,
                   "xscl": 1.0, "yscl": 1.0},
        "angle_mode": "DEG"
    }
    """
    engine = CalculatorEngine()
    angle = body.get("angle_mode", "DEG")
    engine.set_angle_mode(angle)

    gm = GraphMode(engine)
    for i, fn in enumerate(body.get("functions", [])):
        if i < 3:
            gm.set_function(i, fn)

    window = body.get("window", {})
    if window:
        gm.set_window(**window)

    svg = gm.plot()
    return {"svg": svg, "window": gm.window}


# ── Table endpoint ────────────────────────────────────────────────────────────

@app.post("/api/table/generate")
async def table_generate(body: dict):
    """Generate F(X) value table.

    Body: {
        "function": "X**2",
        "start": 1, "end": 5, "step": 1,
        "angle_mode": "DEG"
    }
    Returns: {"rows": [{"x": "1", "y": "1"}, ...], "error": null}
    """
    engine = CalculatorEngine()
    angle = body.get("angle_mode", "DEG")
    engine.set_angle_mode(angle)

    tm = TableMode(engine)
    tm.set_function(body.get("function", ""))
    tm.set_range(
        body.get("start", 1),
        body.get("end", 5),
        body.get("step", 1),
    )
    return tm.generate()


# ── WebSocket — one session = one calculator instance ────────────────────────

@app.websocket("/ws/calculator")
async def websocket_calculator(websocket: WebSocket):
    await websocket.accept()
    engine = CalculatorEngine()
    comp = CompMode(engine)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Invalid JSON"})
                )
                continue

            msg_type = msg.get("type", "key")

            if msg_type == "key":
                key = msg.get("key", "")
                state = comp.handle_key(key)
                await websocket.send_text(json.dumps(state))

            elif msg_type == "reset":
                engine = CalculatorEngine()
                comp = CompMode(engine)
                await websocket.send_text(json.dumps(comp.state.to_dict()))

            else:
                # Echo unknown messages (Phase 1 compatibility)
                await websocket.send_text(raw)

    except WebSocketDisconnect:
        pass
