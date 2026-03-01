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
from app.calculator.modes.stat import StatMode
from app.calculator.modes.matrix import MatrixMode
from app.calculator.modes.equation import EquationMode
from app.calculator.modes.base_n import BaseNMode
from app.calculator.modes.conics import ConicsMode
from app.calculator.modes.program import CasioBasicInterpreter

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

@app.post("/api/graph/pixels")
async def graph_pixels(body: dict):
    """Plot Y= functions and return a 128×64 binary pixel map.

    Body: same as /api/graph/plot.
    Returns: {"pixels": [0|1, ...8192...], "width": 128, "height": 64}
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

    pixels = gm.plot_pixels()
    return {"pixels": pixels, "width": 128, "height": 64}


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


# ── STAT endpoints ────────────────────────────────────────────────────────────

@app.post("/api/stat/one_var")
async def stat_one_var(body: dict):
    """Compute 1-variable statistics.
    Body: {"x": [1, 2, 3, ...]}
    """
    sm = StatMode()
    x = [float(v) for v in body.get("x", [])]
    return sm.one_var(x)


@app.post("/api/stat/two_var")
async def stat_two_var(body: dict):
    """Compute 2-variable statistics.
    Body: {"x": [...], "y": [...]}
    """
    sm = StatMode()
    x = [float(v) for v in body.get("x", [])]
    y = [float(v) for v in body.get("y", [])]
    return sm.two_var(x, y)


@app.post("/api/stat/regression")
async def stat_regression(body: dict):
    """Compute regression.
    Body: {"x": [...], "y": [...], "type": "linear"}
    type: linear | quadratic | logarithmic | exponential | power
    """
    sm = StatMode()
    x = [float(v) for v in body.get("x", [])]
    y = [float(v) for v in body.get("y", [])]
    reg_type = body.get("type", "linear")
    return sm.regression(x, y, reg_type)


# ── MAT endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/matrix/define")
async def matrix_define(body: dict):
    """Define a named matrix.
    Body: {"name": "A", "rows": [[1,2],[3,4]]}
    """
    mm = MatrixMode()
    # We need a shared matrix store — use module-level singleton
    return _matrix_mode().define(
        body.get("name", "A"),
        body.get("rows", []),
    )


@app.post("/api/matrix/calculate")
async def matrix_calculate(body: dict):
    """Perform a matrix operation.
    Body: {"op": "add"|"sub"|"mul"|"scalar_mul"|"transpose"|"det"|"inv"|"rref",
           "a": "A", "b": "B",  (for binary ops)
           "scalar": 2.0,        (for scalar_mul)
           "matrices": {"A": [[...]], "B": [[...]]}}
    """
    mm = MatrixMode()
    # Load matrices from request
    for name, data in body.get("matrices", {}).items():
        mm.define(name, data)

    op = body.get("op", "")
    a = body.get("a", "A")
    b = body.get("b", "B")

    if op == "add":
        return mm.add(a, b)
    elif op == "sub":
        return mm.subtract(a, b)
    elif op == "mul":
        return mm.multiply(a, b)
    elif op == "scalar_mul":
        return mm.scalar_multiply(float(body.get("scalar", 1)), a)
    elif op == "transpose":
        return mm.transpose(a)
    elif op == "det":
        return mm.determinant(a)
    elif op == "inv":
        return mm.inverse(a)
    elif op == "rref":
        return mm.rref(a)
    else:
        return {"error": "Argument ERROR"}


def _matrix_mode():
    """Return a fresh MatrixMode (stateless per request for now)."""
    return MatrixMode()


# ── EQUA endpoints ────────────────────────────────────────────────────────────

@app.post("/api/equa/polynomial")
async def equa_polynomial(body: dict):
    """Solve polynomial equation.
    Body: {"coefficients": [1, 0, -4]}  → x² - 4 = 0
    Coefficients: highest-degree first.
    """
    em = EquationMode()
    coeffs = [float(c) for c in body.get("coefficients", [])]
    return em.polynomial(coeffs)


@app.post("/api/equa/simultaneous")
async def equa_simultaneous(body: dict):
    """Solve simultaneous linear equations.
    Body: {"matrix": [[2,1],[1,3]], "constants": [5,10]}
    """
    em = EquationMode()
    matrix = [[float(v) for v in row] for row in body.get("matrix", [])]
    constants = [float(v) for v in body.get("constants", [])]
    return em.simultaneous(matrix, constants)


# ── BASE-N endpoints ──────────────────────────────────────────────────────────

@app.post("/api/basen/convert")
async def basen_convert(body: dict):
    """Convert a number between bases.
    Body: {"value": "FF", "from_base": "HEX", "to_base": "DEC"}
    Bases: DEC | HEX | BIN | OCT
    """
    bn = BaseNMode()
    return bn.convert(
        str(body.get("value", "0")),
        body.get("from_base", "DEC"),
        body.get("to_base", "DEC"),
    )


@app.post("/api/basen/bitwise")
async def basen_bitwise(body: dict):
    """Perform a bitwise operation.
    Body: {"op": "and"|"or"|"xor"|"not"|"shl"|"shr",
           "a": 12, "b": 10, "bits": 1}
    """
    bn = BaseNMode()
    op = body.get("op", "").lower()
    a = int(body.get("a", 0))
    b = int(body.get("b", 0))
    bits = int(body.get("bits", 1))

    if op == "and":
        return bn.bitwise_and(a, b)
    elif op == "or":
        return bn.bitwise_or(a, b)
    elif op == "xor":
        return bn.bitwise_xor(a, b)
    elif op == "not":
        return bn.bitwise_not(a)
    elif op == "shl":
        return bn.shift_left(a, bits)
    elif op == "shr":
        return bn.shift_right(a, bits)
    else:
        return {"error": "Argument ERROR"}


# ── CONICS endpoint ───────────────────────────────────────────────────────────

@app.post("/api/conics/plot")
async def conics_plot(body: dict):
    """Plot a conic section and return inline SVG.
    Body: {"type": "circle", "params": {"h": 0, "k": 0, "r": 3}}
    type: parabola | circle | ellipse | hyperbola
    """
    cm = ConicsMode()
    return cm.plot(
        body.get("type", "circle"),
        body.get("params", {}),
    )


# ── PRGM endpoints ────────────────────────────────────────────────────────────

_PROGRAMS_DIR = os.path.join(os.path.dirname(__file__), "programs")


@app.get("/api/prgm/list")
async def prgm_list():
    """List available Casio BASIC programs stored on the server."""
    if not os.path.isdir(_PROGRAMS_DIR):
        return {"programs": []}
    names = sorted(
        fn[:-4] for fn in os.listdir(_PROGRAMS_DIR) if fn.endswith(".cas")
    )
    return {"programs": names}


@app.get("/api/prgm/{name}")
async def prgm_get(name: str):
    """Return the source code of a named program."""
    path = os.path.join(_PROGRAMS_DIR, name + ".cas")
    if not os.path.isfile(path):
        return {"error": "Program not found"}
    with open(path, encoding="utf-8") as f:
        return {"name": name, "source": f.read()}


@app.post("/api/prgm/save")
async def prgm_save(body: dict):
    """Save (create or overwrite) a named program.
    Body: {"name": "MYPROG", "source": "...casio basic..."}
    """
    name   = body.get("name", "").strip()
    source = body.get("source", "")
    if not name:
        return {"error": "Name required"}
    os.makedirs(_PROGRAMS_DIR, exist_ok=True)
    path = os.path.join(_PROGRAMS_DIR, name + ".cas")
    with open(path, "w", encoding="utf-8") as f:
        f.write(source)
    return {"status": "ok", "name": name}


@app.delete("/api/prgm/{name}")
async def prgm_delete(name: str):
    """Delete a named program."""
    path = os.path.join(_PROGRAMS_DIR, name + ".cas")
    if os.path.isfile(path):
        os.remove(path)
        return {"status": "ok"}
    return {"error": "Not found"}


@app.post("/api/prgm/run")
async def prgm_run(body: dict):
    """Run a Casio BASIC program and return all output events.

    Body: {
        "source": "...program text...",
        "inputs": [3, 4, ...],   // pre-supplied Input values
        "name":   "PROGNAME",    // alternative: load by name
        "angle_mode": "DEG"
    }
    Returns: {
        "events": [...],
        "variables": {"A": 0, ...},
        "error": null | "...",
        "terminated": false
    }
    """
    source = body.get("source", "")
    if not source:
        name = body.get("name", "")
        path = os.path.join(_PROGRAMS_DIR, name + ".cas")
        if name and os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                source = f.read()
        else:
            return {"error": "No source provided", "events": [], "variables": {}}

    inputs     = body.get("inputs", [])
    angle_mode = body.get("angle_mode", "DEG")

    interp = CasioBasicInterpreter(angle_mode=angle_mode)

    # Make server-stored programs available for Prog "name" calls
    if os.path.isdir(_PROGRAMS_DIR):
        for fn in os.listdir(_PROGRAMS_DIR):
            if fn.endswith(".cas"):
                prog_name = fn[:-4]
                with open(os.path.join(_PROGRAMS_DIR, fn), encoding="utf-8") as f:
                    interp.programs[prog_name] = f.read()

    result = interp.run(source, inputs)
    return {
        "events":     result.events,
        "variables":  result.variables,
        "error":      result.error,
        "terminated": result.terminated,
    }


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
