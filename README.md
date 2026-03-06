# Casio CFX-9850G Web Emulator

A faithful browser-based emulation of the Casio CFX-9850G Color Power Graphic Calculator, built as a FastAPI web application.

![Calculator screenshot](https://via.placeholder.com/600x400?text=Casio+CFX-9850G+Emulator)

## Features

- **Dot-matrix LCD** — 128×64 pixel display rendered on HTML5 canvas, 3× scaled with the CFX-9850G's characteristic amber/green color
- **All major calculator modes** accessible from the MENU screen
- **Casio BASIC interpreter** — runs programs downloaded from the internet
- **CAT file support** — load `.cat` files from Casio FA-122/FA-123/FA-124 software directly

### Modes

| # | Mode | Description |
|---|------|-------------|
| 1 | RUN/COMP | Arithmetic, trig, logarithms, complex numbers, variables A–Z |
| 2 | STAT | 1-var statistics, 2-var regression, statistical graphs |
| 3 | GRAPH | Plot Y= functions, zoom, trace, V-Window settings |
| 4 | — | (DYNA placeholder) |
| 5 | TABLE | Generate value tables from F(X) with start/end/step |
| 6 | — | (RECR placeholder) |
| 7 | EQUA | Polynomial solver (up to degree 6), simultaneous equations (up to 6×6) |
| 8 | PRGM | Casio BASIC editor, runner, and file loader |
| 9 | MAT | Matrix arithmetic, determinant, inverse, RREF |

### PRGM / Casio BASIC

The built-in interpreter supports the full CFX-9850G BASIC command set:

- **Display:** `Locate`, `ClrText`, `ClrGraph`, `Text`, `Circle`, `F-Line`
- **Flow:** `If`/`Then`/`Else`/`IfEnd`, `For`/`To`/`Step`/`Next`, `While`/`WhileEnd`, `Do`/`LpWhile`, `Lbl`/`Goto`, `Prog`, `Return`, `Stop`
- **I/O:** `Input`, `Print`, `?`, `◢` (pause), `Getkey`
- **Graphics:** `ViewWindow`, `Graph Y=`, `PlotOn`/`PlotOff`/`PlotChg`, `Line`, `DrawStat`
- **Math:** `value→var`, `Dim List`, `List n`, `Int`, `Frac`, `Abs`, `Ran#`
- **Operators:** `⇒` (single-line conditional), `→` (store)

Five example programs are bundled: `fibonacci`, `primes`, `quadratic`, `bounce`, `input_test`.

## Quick Start

### Requirements

- Python 3.12+
- pip

### Install

```bash
git clone <repo-url>
cd casio-cfx9850g
pip install -r requirements.txt
```

### Run

```bash
uvicorn app.main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

## Project Structure

```
casio-cfx9850g/
├── app/
│   ├── main.py                    # FastAPI app, all API routes
│   ├── calculator/
│   │   ├── engine.py              # SymPy expression evaluator
│   │   ├── cat_parser.py          # FA-122/FA-123/FA-124 CAT file parser
│   │   ├── memory.py              # Variable store (A–Z, Ans, Matrices A–F)
│   │   └── modes/
│   │       ├── comp.py            # COMP mode
│   │       ├── graph.py           # GRAPH mode (Matplotlib → SVG)
│   │       ├── table.py           # TABLE mode
│   │       ├── stat.py            # STAT mode
│   │       ├── matrix.py          # MAT mode
│   │       ├── equation.py        # EQUA mode
│   │       ├── program.py         # Casio BASIC interpreter
│   │       ├── base_n.py          # BASE-N mode
│   │       └── conics.py          # CONICS mode
│   ├── programs/                  # Bundled .cas example programs
│   └── static/
│       ├── index.html
│       ├── css/
│       │   ├── calculator.css     # Calculator body and key styling
│       │   └── screen.css         # LCD display styling
│       └── js/
│           ├── app.js             # Entry point, key handler, mode state machines
│           ├── keyboard.js        # Physical key mapping
│           ├── display.js         # LCD canvas renderer
│           ├── modes.js           # Mode definitions and soft-key labels
│           └── graph.js           # Graph canvas
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_comp.py
│   ├── test_graph.py
│   ├── test_table.py
│   ├── test_stat.py
│   ├── test_matrix.py
│   ├── test_equation.py
│   ├── test_base_n.py
│   ├── test_menu_navigation.py
│   ├── test_basic_interpreter.py
│   └── basic_programs/            # .cas fixture files for BASIC tests
├── requirements.txt
└── CLAUDE.md
```

## API Reference

### Calculator

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/calc` | Evaluate a COMP-mode expression |
| GET | `/api/graph/plot` | Plot a function, returns inline SVG |
| GET | `/api/table/generate` | Generate a value table |

### Programs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/prgm/list` | List stored programs (`.cas` and `.cat`) |
| GET | `/api/prgm/{name}` | Get program source (CAT files auto-converted) |
| POST | `/api/prgm/save` | Save a program |
| POST | `/api/prgm/run` | Run a program, returns output events |
| DELETE | `/api/prgm/{name}` | Delete a program |

### WebSocket

Connect to `/ws/calculator` for real-time key events and display updates.

## Loading Programs

### From the UI

In PRGM mode, press **F4** to open a file picker. Supported formats:
- `.cas` — plain-text Casio BASIC (one statement per line)
- `.cat` — FA-122/FA-123/FA-124 catalog files (auto-converted on load)
- `.txt` — plain text, treated as `.cas`

### CAS format

Plain UTF-8 text, one statement per line. Use `->` or `→` for the store arrow, `//` for comments:

```
// Quadratic formula
Input "A=",A
Input "B=",B
Input "C=",C
B*B-4*A*C→D
If D<0
Then
"No real roots"
IfEnd
(-B+sqrt(D))/(2*A)→X
Print X
```

### CAT format

Files exported from Casio's FA-122/FA-123/FA-124 PC-link software. The emulator parses the `%Header Record` / `%Data Record` structure and converts all backslash tokens (`\->`, `\=>`, `\Goto`, etc.) to plain-text CAS format automatically.

## Running Tests

```bash
pytest tests/ -v
```

418 tests covering all modes and the BASIC interpreter.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI 0.111, Python 3.12 |
| Math | NumPy, SymPy, SciPy |
| Graphing | Matplotlib (server-side SVG) |
| Frontend | Vanilla HTML5/CSS3/JS — no frameworks |
| Real-time | WebSocket via FastAPI |
| Tests | pytest, httpx, pytest-asyncio |

## Accuracy Notes

- Angles default to **DEG** mode (matching CFX-9850G factory default)
- Division by zero → `Math ERROR` (exact CFX-9850G error string)
- Float display: up to 10 significant figures
- Complex output: `a+bi` format (not Python's `a+bj`)
- Matrix indices are 1-based in the UI, matching the real calculator
