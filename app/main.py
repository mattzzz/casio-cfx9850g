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
from app.calculator.cat_parser import (
    is_cat_file, parse_cat_file, parse_cat_programs, parse_cat_matrices, find_entry_point,
)

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


def _find_program_path(name: str) -> str | None:
    """Return the filesystem path for a program, checking .cas then .cat."""
    for ext in (".cas", ".cat"):
        path = os.path.join(_PROGRAMS_DIR, name + ext)
        if os.path.isfile(path):
            return path
    return None


def _load_program_source(path: str) -> str:
    """Read a program file and return its plain-text CAS source.

    CAT files are transparently converted before returning (first record).
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if path.endswith(".cat") or is_cat_file(content):
        _, source = parse_cat_file(content)
        return source
    return content


def _find_program_in_cats(name: str) -> str | None:
    """Search all .cat files in the programs dir for a program by name.

    Returns the converted CAS source if found, else None.
    """
    result = _find_cat_for_program(name)
    return result[1] if result else None


def _find_cat_for_program(name: str) -> tuple[str, str] | None:
    """Search all .cat files for a program named *name*.

    Returns (cat_content, program_source) so callers can also load
    sub-programs and matrices from the same CAT file.
    """
    if not os.path.isdir(_PROGRAMS_DIR):
        return None
    for fn in os.listdir(_PROGRAMS_DIR):
        if not fn.endswith(".cat"):
            continue
        path = os.path.join(_PROGRAMS_DIR, fn)
        with open(path, encoding="utf-8") as f:
            cat_content = f.read()
        for pname, src in parse_cat_programs(cat_content):
            if pname == name:
                return cat_content, src
    return None


@app.get("/api/prgm/list")
async def prgm_list():
    """List available Casio BASIC programs stored on the server.

    Multi-record .cat files contribute ONE entry — the entry-point program
    (the program not called by any other program in the file).  Any .cas
    files that are sub-programs of a stored .cat file are suppressed so
    they do not appear as separate list entries.
    """
    if not os.path.isdir(_PROGRAMS_DIR):
        return {"programs": []}

    names: set[str] = set()
    cat_subprograms: set[str] = set()  # all names from .cat files (including non-entry)

    for fn in sorted(os.listdir(_PROGRAMS_DIR)):
        if fn.endswith(".cat"):
            path = os.path.join(_PROGRAMS_DIR, fn)
            with open(path, encoding="utf-8") as f:
                cat_content = f.read()
            programs = parse_cat_programs(cat_content)
            if programs:
                names.add(find_entry_point(programs))
                for pname, _ in programs:
                    cat_subprograms.add(pname)

    for fn in sorted(os.listdir(_PROGRAMS_DIR)):
        if fn.endswith(".cas"):
            prog_name = fn[:-4]
            if prog_name not in cat_subprograms:
                names.add(prog_name)

    return {"programs": sorted(names)}


@app.get("/api/prgm/{name}")
async def prgm_get(name: str):
    """Return the source code of a named program."""
    path = _find_program_path(name)
    if path:
        return {"name": name, "source": _load_program_source(path)}
    # Not a standalone file — search inside multi-record .cat files
    src = _find_program_in_cats(name)
    if src is not None:
        return {"name": name, "source": src}
    return {"error": "Program not found"}


@app.post("/api/prgm/save")
async def prgm_save(body: dict):
    """Save (create or overwrite) a named program.

    Body: {"name": "MYPROG", "source": "...casio basic...", "ext": ".cas"}

    If *source* is a multi-record CAT file all contained programs are
    extracted and saved individually as .cas files.  The primary program
    name (first record) is returned.
    """
    name   = body.get("name", "").strip()
    source = body.get("source", "")
    ext    = body.get("ext", ".cas")
    if ext not in (".cas", ".cat"):
        ext = ".cas"
    if not name:
        return {"error": "Name required"}
    os.makedirs(_PROGRAMS_DIR, exist_ok=True)

    # Multi-record CAT file: extract all programs and save each individually
    if ext == ".cat" and is_cat_file(source):
        programs = parse_cat_programs(source)
        if programs:
            entry_name = find_entry_point(programs)
            for prog_name, prog_source in programs:
                path = os.path.join(_PROGRAMS_DIR, prog_name + ".cas")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(prog_source)
            return {"status": "ok", "name": entry_name, "count": len(programs)}
        # Fallthrough: empty CAT — save raw

    path = os.path.join(_PROGRAMS_DIR, name + ext)
    with open(path, "w", encoding="utf-8") as f:
        f.write(source)
    return {"status": "ok", "name": name}


@app.delete("/api/prgm/{name}")
async def prgm_delete(name: str):
    """Delete a named program."""
    path = _find_program_path(name)
    if path and os.path.isfile(path):
        os.remove(path)
        return {"status": "ok"}
    return {"error": "Not found"}


@app.post("/api/prgm/run")
async def prgm_run(body: dict):
    """Run a Casio BASIC program and return all output events.

    Body: {
        "source": "...program text...",
        "inputs": [3, 4, ...],      // pre-supplied Input values
        "name":   "PROGNAME",       // alternative: load by name
        "angle_mode": "DEG",
        "getkey": 0,                // Casio key code active this frame
        "start_label": "A",         // start execution from this Lbl (game loop)
        "state": {                  // restore state for game frames
            "variables": {"A": 0, ...},
            "matrices":  {"A": [[...]]}
        }
    }
    Returns: {
        "events": [...],
        "variables": {"A": 0, ...},
        "matrices": {"A": [[...]]},
        "executing_prog": "TETMAIN",  // program name when MAX_ITERATIONS hit
        "error": null | "...",
        "terminated": false
    }
    """
    source = body.get("source", "")
    raw_cat_source: str | None = None   # remember original CAT if passed directly

    if not source:
        name = body.get("name", "")
        path = _find_program_path(name) if name else None
        if path:
            source = _load_program_source(path)
            if path.endswith(".cat"):
                with open(path, encoding="utf-8") as _f:
                    raw_cat_source = _f.read()
        else:
            # Program might live inside a multi-record CAT file (e.g. P1 in doom.cat)
            cat_result = _find_cat_for_program(name) if name else None
            if cat_result:
                raw_cat_source, source = cat_result
            else:
                return {"error": "No source provided", "events": [], "variables": {}}
    elif is_cat_file(source):
        # Raw CAT source passed directly (e.g. from frontend file load)
        raw_cat_source = source
        programs = parse_cat_programs(source)
        if programs:
            entry = find_entry_point(programs)
            source = next((s for n, s in programs if n == entry), programs[0][1])
        else:
            source = ""

    inputs      = body.get("inputs", [])
    angle_mode  = body.get("angle_mode", "DEG")
    getkey      = int(body.get("getkey", 0))
    start_label = body.get("start_label") or None
    state       = body.get("state") or {}
    state_vars  = state.get("variables", {}) if state else {}
    state_mats  = state.get("matrices", {}) if state else {}

    interp = CasioBasicInterpreter(angle_mode=angle_mode)

    # Load matrices from the directly-provided CAT (e.g. tetris.cat Mat A record)
    if raw_cat_source:
        for mat_letter, mat_data in parse_cat_matrices(raw_cat_source):
            interp.matrices[mat_letter] = mat_data
        # Also load ALL programs from the same CAT as sub-programs
        for pname, psrc in parse_cat_programs(raw_cat_source):
            interp.programs[pname] = psrc

    # Make server-stored programs available for Prog "name" calls.
    # Multi-record .cat files expose ALL their programs, not just the first.
    if os.path.isdir(_PROGRAMS_DIR):
        for fn in os.listdir(_PROGRAMS_DIR):
            prog_path = os.path.join(_PROGRAMS_DIR, fn)
            if fn.endswith(".cat"):
                with open(prog_path, encoding="utf-8") as f:
                    cat_content = f.read()
                for pname, psrc in parse_cat_programs(cat_content):
                    interp.programs[pname] = psrc
                for mat_letter, mat_data in parse_cat_matrices(cat_content):
                    if mat_letter not in interp.matrices:
                        interp.matrices[mat_letter] = mat_data
            elif fn.endswith(".cas"):
                prog_name = fn[:-4]
                # Don't overwrite programs already loaded from a .cat file
                if prog_name not in interp.programs:
                    interp.programs[prog_name] = _load_program_source(prog_path)

    prog_name = body.get("name", "main") or "main"
    result = interp.run(
        source, inputs,
        key=getkey,
        start_label=start_label,
        state_variables=state_vars,
        state_matrices=state_mats,
        prog_name=prog_name,
    )
    return {
        "events":         result.events,
        "variables":      result.variables,
        "matrices":       result.matrices,
        "executing_prog": result.executing_prog,
        "error":          result.error,
        "terminated":     result.terminated,
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
