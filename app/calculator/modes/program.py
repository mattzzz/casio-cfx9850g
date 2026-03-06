"""Casio BASIC interpreter for CFX-9850G — Phase 6.

Supports:
  Display:   Locate x,y,text  ClrText  ClrGraph  ClrList
  Flow:      If/Then/Else/IfEnd  For/To/Step/Next  While/WhileEnd
             Do/LpWhile  Lbl/Goto  Prog/Return/Stop
  I/O:       Input  Print  ? (shorthand)  ◢ (pause)  Getkey
  Graphics:  ViewWindow  Graph Y=  PlotOn/Off/Chg  Line  F-Line  DrawStat
  Math:      value→var  Dim List  List n

Source-file conventions:
  - UTF-8 text, one statement per line (or separated by ':' on same line)
  - ASCII alternatives: '->' for →, '>>' for ◢
  - Line comments starting with '//'
"""

from __future__ import annotations

import random
import re
import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

MAX_ITERATIONS = 3_000
MAX_CALL_DEPTH  = 256

# Fast-path regexes — match before calling SymPy
_PURE_NUM_RE = re.compile(r'^-?\d+(\.\d+)?([eE][+-]?\d+)?$')
_PURE_VAR_RE = re.compile(r'^([A-Zθr])$')


# ── Value formatting ─────────────────────────────────────────────────────────

def _fmt(val: float) -> str:
    """Format a numeric value as the CFX-9850G would display it."""
    if val == int(val) and abs(val) < 1e15:
        return str(int(val))
    return f"{val:.10g}"


# ── Expression evaluator ──────────────────────────────────────────────────────

def _local_dict(variables: dict, angle_mode: str = "DEG", current_key: int = 0) -> dict:
    """Build a SymPy local_dict including Casio BASIC variables and functions."""
    if angle_mode == "DEG":
        k, rk = sp.pi / 180, sp.Integer(180) / sp.pi
    elif angle_mode == "GRD":
        k, rk = sp.pi / 200, sp.Integer(200) / sp.pi
    else:
        k, rk = sp.Integer(1), sp.Integer(1)

    d: dict = {
        "pi": sp.pi, "e": sp.E, "i": sp.I,
        "sin":  lambda x: sp.sin(x * k),
        "cos":  lambda x: sp.cos(x * k),
        "tan":  lambda x: sp.tan(x * k),
        "asin": lambda x: sp.asin(x) * rk,
        "acos": lambda x: sp.acos(x) * rk,
        "atan": lambda x: sp.atan(x) * rk,
        "sqrt": sp.sqrt,
        "log":  lambda x: sp.log(x, 10),
        "ln":   sp.log,
        "abs":  sp.Abs, "Abs": sp.Abs,
        "Int":  lambda x: sp.floor(x),
        "Frac": lambda x: x - sp.floor(x),
        "Rnd":  lambda x: sp.Float(round(float(x.evalf()), 0)),
        "Ran":  lambda: sp.Float(0.5),  # placeholder
        "Getkey": sp.Float(current_key),
    }
    for name, val in variables.items():
        if isinstance(val, (int, float)):
            d[name] = sp.Float(val)
        elif isinstance(val, sp.Basic):
            d[name] = val
    return d


def _substitute_mat_refs(
    expr: str, variables: dict, angle_mode: str, matrices: dict
) -> str:
    """Replace Mat X[r,c] references with their numeric values."""
    def _replace(m: re.Match) -> str:
        mat_name = m.group(1).upper()
        try:
            r = int(round(_eval(m.group(2), variables, angle_mode, None)))
            c = int(round(_eval(m.group(3), variables, angle_mode, None)))
            mat = matrices.get(mat_name)
            if mat and 1 <= r <= len(mat) and 1 <= c <= len(mat[r - 1]):
                return str(float(mat[r - 1][c - 1]))
        except Exception:
            pass
        return "0"
    return _MAT_REF_RE.sub(_replace, expr)


def _eval(
    expr_str: str,
    variables: dict,
    angle_mode: str = "DEG",
    matrices: dict | None = None,
    current_key: int = 0,
) -> float:
    """Evaluate a Casio BASIC expression. Returns float. Raises ValueError on error."""
    s = expr_str.strip()
    if not s:
        raise ValueError("Empty expression")

    # ── Fast paths (bypass SymPy for common cases) ────────────────────────
    if _PURE_NUM_RE.match(s):
        return float(s)
    if s == 'Getkey':
        return float(current_key)
    _vm = _PURE_VAR_RE.match(s)
    if _vm:
        v = variables.get(_vm.group(1), 0.0)
        return float(v) if isinstance(v, (int, float)) else float(complex(v).real)

    # Ran# contains '#' which is not a valid SymPy identifier — substitute value now
    if 'Ran#' in s:
        s = s.replace('Ran#', str(random.random()))
    # Substitute matrix element references before parsing
    if matrices and 'Mat' in s:
        s = _substitute_mat_refs(s, variables, angle_mode, matrices)
    ld = _local_dict(variables, angle_mode, current_key)
    try:
        result = parse_expr(s, local_dict=ld, transformations=_TRANSFORMS)
        # Check for symbolic infinities / undefined
        if result in (sp.zoo, sp.oo, sp.nan, -sp.oo):
            raise ValueError("Math ERROR")
        if result.is_number is False and hasattr(result, "is_Relational") and result.is_Relational:
            raise ValueError("Syntax ERROR: relational in numeric context")
        evaled = result.evalf(15)
        if evaled in (sp.zoo, sp.oo, sp.nan, -sp.oo):
            raise ValueError("Math ERROR")
        val = complex(evaled)
        if abs(val.imag) > 1e-9:
            raise ValueError("Non-real result")
        return float(val.real)
    except ValueError:
        raise
    except (TypeError, ZeroDivisionError):
        raise ValueError("Math ERROR")
    except Exception as exc:
        raise ValueError(f"Syntax ERROR: {exc}") from exc


def _strip_outer_parens(s: str) -> str:
    """Remove one layer of parentheses if they wrap the entire string."""
    if not (s.startswith('(') and s.endswith(')')):
        return s
    depth = 0
    for i, c in enumerate(s):
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        # If depth reaches 0 before the last character the outer parens
        # are NOT wrapping everything — do not strip.
        if depth == 0 and i < len(s) - 1:
            return s
    return s[1:-1]


def _eval_cond(
    cond: str,
    variables: dict,
    angle_mode: str = "DEG",
    matrices: dict | None = None,
    current_key: int = 0,
) -> bool:
    """Evaluate a boolean condition. Returns True/False."""
    s = _strip_outer_parens(cond.strip())
    # Handle compound And / Or conditions (split on word boundary)
    for logic_op in (' And ', ' Or '):
        if logic_op in s:
            parts = s.split(logic_op)
            results = [_eval_cond(p, variables, angle_mode, matrices, current_key) for p in parts]
            if ' And ' in logic_op:
                return all(results)
            else:
                return any(results)
    # Normalise Unicode relational operators and CAT-format <> not-equal
    s = s.replace("≥", ">=").replace("≤", "<=").replace("≠", "!=").replace("<>", "!=")

    # Try two-char operators first, then one-char
    for op in (">=", "<=", "!=", ">", "<"):
        idx = s.find(op)
        if idx > 0:
            lv = _eval(s[:idx].strip(), variables, angle_mode, matrices, current_key)
            rv = _eval(s[idx + len(op):].strip(), variables, angle_mode, matrices, current_key)
            if op == ">=": return lv >= rv
            if op == "<=": return lv <= rv
            if op == "!=": return lv != rv
            if op == ">":  return lv >  rv
            if op == "<":  return lv <  rv

    # Single '=' is equality in Casio BASIC conditions
    idx = s.find("=")
    if idx > 0:
        lv = _eval(s[:idx].strip(), variables, angle_mode, matrices, current_key)
        rv = _eval(s[idx + 1:].strip(), variables, angle_mode, matrices, current_key)
        return abs(lv - rv) < 1e-9

    # No comparison operator — numeric truth (non-zero)
    try:
        return _eval(s, variables, angle_mode, matrices, current_key) != 0.0
    except ValueError:
        return False


# ── Statement ─────────────────────────────────────────────────────────────────

class Statement:
    """A single parsed Casio BASIC statement."""
    __slots__ = ("cmd", "args", "raw", "line_no")

    def __init__(self, cmd: str, args: dict, raw: str = "", line_no: int = 0):
        self.cmd     = cmd
        self.args    = args
        self.raw     = raw
        self.line_no = line_no

    def __repr__(self) -> str:
        return f"<Stmt {self.cmd} args={self.args} line={self.line_no}>"


# ── Parser helpers ────────────────────────────────────────────────────────────

def _normalise(s: str) -> str:
    """Replace ASCII shorthands with Unicode Casio BASIC characters."""
    return s.replace("->", "→").replace(">>", "◢")


def _split_colon(line: str) -> list[str]:
    """Split on ':' while respecting quoted strings."""
    parts, cur, in_q = [], [], False
    for ch in line:
        if ch == '"':
            in_q = not in_q
            cur.append(ch)
        elif ch == ":" and not in_q:
            s = "".join(cur).strip()
            if s:
                parts.append(s)
            cur = []
        else:
            cur.append(ch)
    s = "".join(cur).strip()
    if s:
        parts.append(s)
    return parts


def _split_args(s: str) -> list[str]:
    """Split comma-separated args while respecting parens and quoted strings."""
    parts, cur, depth, in_q = [], [], 0, False
    for ch in s:
        if ch == '"':
            in_q = not in_q
            cur.append(ch)
        elif ch == "(" and not in_q:
            depth += 1
            cur.append(ch)
        elif ch == ")" and not in_q:
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0 and not in_q:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur).strip())
    return parts


# ── Per-statement parser ──────────────────────────────────────────────────────

_ASSIGN_RE   = re.compile(r"^(.+?)\s*→\s*([A-Zθr])\s*$", re.DOTALL)
# Casio native FOR: For start→var To end [Step step]
_FOR_CAS_RE  = re.compile(
    r"^For\s+(.+?)\s*→\s*([A-Zθr])\s+To\s+(.+?)(?:\s+Step\s+(.+))?$",
    re.IGNORECASE | re.DOTALL,
)
# Legacy BASIC FOR: For var=start To end [Step step]
_FOR_RE      = re.compile(
    r"^For\s+([A-Zθr])\s*=\s*(.+?)\s+To\s+(.+?)(?:\s+Step\s+(.+))?$", re.IGNORECASE
)
_NEXT_RE     = re.compile(r"^Next(?:\s+([A-Zθr]))?$", re.IGNORECASE)
_WHILE_RE    = re.compile(r"^While\s+(.+)$", re.IGNORECASE)
_LPWHILE_RE  = re.compile(r"^LpWhile\s+(.+)$", re.IGNORECASE)
_LBL_RE      = re.compile(r"^Lbl\s+([0-9A-Za-zθr])\s*$")
_GOTO_RE     = re.compile(r"^Goto\s+([0-9A-Za-zθr])\s*$")
_INPUT_RE    = re.compile(r'^Input\s*(?:"([^"]*)"\s*,\s*)?([A-Zθr])\s*$', re.IGNORECASE)
_INPUT_Q_RE  = re.compile(r"^\?\s*→?\s*([A-Zθr])\s*$")
_PRINT_RE    = re.compile(r"^Print\s+(.+)$", re.IGNORECASE)
_LOCATE_RE   = re.compile(r"^Locate\s+(.+)$", re.IGNORECASE)
_VIEW_RE     = re.compile(r"^ViewWindow\s+(.+)$", re.IGNORECASE)
_GRAPH_Y_RE  = re.compile(r"^Graph\s+Y=(.+)$", re.IGNORECASE)
_PLOTON_RE   = re.compile(r"^PlotOn\s+(.+)$", re.IGNORECASE)
_PLOTOFF_RE  = re.compile(r"^PlotOff\s+(.+)$", re.IGNORECASE)
_PLOTCHG_RE  = re.compile(r"^PlotChg\s+(.+)$", re.IGNORECASE)
_PLOT_RE     = re.compile(r"^Plot\s+(.+)$", re.IGNORECASE)   # bare Plot (= PlotOn)
_FLINE_RE    = re.compile(r"^F-Line\s+(.+)$", re.IGNORECASE)
_PROG_RE     = re.compile(r'^Prog\s+"([^"]+)"\s*$', re.IGNORECASE)
_DIM_LIST_RE = re.compile(r"^Dim\s+List\s+(.+)$", re.IGNORECASE)
_LIST_RE     = re.compile(r"^List\s+(\d+)\s*$", re.IGNORECASE)
_DSZ_RE      = re.compile(r"^Dsz\s+([A-Zθr])\s*$", re.IGNORECASE)
_ISZ_RE      = re.compile(r"^Isz\s+([A-Zθr])\s*$", re.IGNORECASE)
# Matrix element assignment:  expr→Mat X[r,c]
_MAT_ASSIGN_RE = re.compile(
    r"^(.+?)\s*→\s*Mat\s+([A-F])\s*\[(.+?),(.+?)\]\s*$",
    re.IGNORECASE | re.DOTALL,
)
# Fill(value, Mat X)
_FILL_RE     = re.compile(r"^Fill\s*\(\s*(.+?)\s*,\s*Mat\s+([A-F])\s*\)?\s*$", re.IGNORECASE)
_IGNORE_RE   = re.compile(
    r"^(AxesOff|AxesOn|GridOff|GridOn|LabelOff|LabelOn|"
    r"Norm|Fix|Sci|Deg|Rad|Gra|DispGraph|DrawGraph|DrawStat|"
    r"Orange|Green|Blue|Cls|Text\b|GotoD\b)",
    re.IGNORECASE,
)
# Regex to find Mat X[r,c] references inside expressions
_MAT_REF_RE  = re.compile(r'Mat\s+([A-F])\[([^\]]+),([^\]]+)\]', re.IGNORECASE)


def parse_stmt(s: str, line_no: int = 0) -> Statement:
    """Parse one Casio BASIC statement string into a Statement object."""
    raw = s

    # Pause / display trigger ◢
    if s == "◢":
        return Statement("PAUSE", {}, raw, line_no)

    # ? shorthand for Input
    m = _INPUT_Q_RE.match(s)
    if m:
        return Statement("INPUT", {"prompt": "?", "var": m.group(1)}, raw, line_no)

    # "prompt"?→VAR — Casio combined display-prompt + input
    m = re.match(r'^"([^"]*)"\s*\?\s*→\s*([A-Zθr])\s*$', s)
    if m:
        return Statement("INPUT", {"prompt": m.group(1), "var": m.group(2)}, raw, line_no)

    # Standalone quoted string display: "text" or "text"◢
    if s.startswith('"'):
        if s.endswith('"') and s.count('"') == 2:
            return Statement("PRINT_STR", {"text": s[1:-1]}, raw, line_no)
        if s.endswith('"◢') and s.count('"') == 2:
            return Statement("PRINT_PAUSE", {"text": s[1:-2]}, raw, line_no)

    # Casio native FOR: For start→var To end [Step step]
    m = _FOR_CAS_RE.match(s)
    if m:
        return Statement("FOR", {
            "var":   m.group(2).strip(),
            "start": m.group(1).strip(),
            "end":   m.group(3).strip(),
            "step":  (m.group(4) or "1").strip(),
        }, raw, line_no)

    # Legacy BASIC FOR: For var=start To end [Step s]
    m = _FOR_RE.match(s)
    if m:
        return Statement("FOR", {
            "var":   m.group(1).upper(),
            "start": m.group(2).strip(),
            "end":   m.group(3).strip(),
            "step":  (m.group(4) or "1").strip(),
        }, raw, line_no)

    # Next [var]
    m = _NEXT_RE.match(s)
    if m:
        return Statement("NEXT", {"var": (m.group(1) or "").upper()}, raw, line_no)

    # While cond
    m = _WHILE_RE.match(s)
    if m:
        return Statement("WHILE", {"cond": m.group(1).strip()}, raw, line_no)

    # WhileEnd
    if s.lower() == "whileend":
        return Statement("WHILEEND", {}, raw, line_no)

    # Do
    if s.lower() == "do":
        return Statement("DO", {}, raw, line_no)

    # LpWhile cond
    m = _LPWHILE_RE.match(s)
    if m:
        return Statement("LPWHILE", {"cond": m.group(1).strip()}, raw, line_no)

    # Break (exit innermost loop)
    if s.lower() == "break":
        return Statement("BREAK", {}, raw, line_no)

    # ── IMPORTANT: If/Then/Else/IfEnd must be checked BEFORE assignment
    # (because "If cond Then expr→VAR" contains → but is NOT an assignment)

    # If — block or inline
    if s[:2].lower() == "if" and (len(s) == 2 or s[2] in (" ", "\t")):
        rest = s[2:].strip()
        tm = re.search(r"\bThen\b", rest, re.IGNORECASE)
        if tm:
            cond = rest[:tm.start()].strip()
            then_part = rest[tm.end():].strip()
            if then_part:
                inline = parse_stmt(then_part, line_no)
                return Statement("IF_INLINE", {"cond": cond, "then_stmt": inline}, raw, line_no)
            else:
                return Statement("IF_BLOCK", {"cond": cond}, raw, line_no)
        else:
            return Statement("IF_BLOCK", {"cond": rest}, raw, line_no)

    # Then (standalone, after If block form)
    if s.lower() == "then":
        return Statement("THEN", {}, raw, line_no)

    # Else
    if s.lower() == "else":
        return Statement("ELSE", {}, raw, line_no)

    # IfEnd
    if s.lower() in ("ifend",):
        return Statement("IFEND", {}, raw, line_no)

    # Matrix element assignment  expr→Mat X[r,c]  (must come before general ASSIGN)
    m = _MAT_ASSIGN_RE.match(s)
    if m:
        return Statement("MAT_ASSIGN", {
            "expr": m.group(1).strip(),
            "mat":  m.group(2).upper(),
            "row":  m.group(3).strip(),
            "col":  m.group(4).strip(),
        }, raw, line_no)

    # Assignment  expr→VAR  (must come after If/Then/Else/IfEnd checks)
    m = _ASSIGN_RE.match(s)
    if m:
        return Statement("ASSIGN", {"expr": m.group(1).strip(), "var": m.group(2)}, raw, line_no)

    # Lbl n
    m = _LBL_RE.match(s)
    if m:
        return Statement("LBL", {"label": m.group(1)}, raw, line_no)

    # Goto n
    m = _GOTO_RE.match(s)
    if m:
        return Statement("GOTO", {"label": m.group(1)}, raw, line_no)

    # Input ["prompt",]VAR
    m = _INPUT_RE.match(s)
    if m:
        return Statement("INPUT", {
            "prompt": m.group(1) or "?",
            "var":    m.group(2).upper(),
        }, raw, line_no)

    # Print expr
    m = _PRINT_RE.match(s)
    if m:
        return Statement("PRINT_EXPR", {"expr": m.group(1).strip()}, raw, line_no)

    # Locate x,y,text
    m = _LOCATE_RE.match(s)
    if m:
        args = _split_args(m.group(1))
        if len(args) >= 3:
            return Statement("LOCATE", {"x": args[0], "y": args[1], "text": args[2]}, raw, line_no)

    # ClrText / ClrGraph / ClrList
    if s.lower() == "clrtext":
        return Statement("CLRTEXT", {}, raw, line_no)
    if s.lower() == "clrgraph":
        return Statement("CLRGRAPH", {}, raw, line_no)
    if s.lower() == "clrlist":
        return Statement("CLRLIST", {}, raw, line_no)

    # ViewWindow xmin,xmax,xscl,ymin,ymax,yscl
    m = _VIEW_RE.match(s)
    if m:
        return Statement("VIEWWINDOW", {"args": _split_args(m.group(1))}, raw, line_no)

    # Graph Y=expr
    m = _GRAPH_Y_RE.match(s)
    if m:
        return Statement("GRAPH_Y", {"expr": m.group(1).strip()}, raw, line_no)

    # PlotOn / PlotOff / PlotChg
    m = _PLOTON_RE.match(s)
    if m:
        args = _split_args(m.group(1))
        return Statement("PLOTON",  {"x": args[0], "y": args[1] if len(args) > 1 else "0"}, raw, line_no)
    m = _PLOTOFF_RE.match(s)
    if m:
        args = _split_args(m.group(1))
        return Statement("PLOTOFF", {"x": args[0], "y": args[1] if len(args) > 1 else "0"}, raw, line_no)
    m = _PLOTCHG_RE.match(s)
    if m:
        args = _split_args(m.group(1))
        return Statement("PLOTCHG", {"x": args[0], "y": args[1] if len(args) > 1 else "0"}, raw, line_no)

    # Plot x,y (bare — equivalent to PlotOn; used in many CAT-format programs)
    m = _PLOT_RE.match(s)
    if m:
        args = _split_args(m.group(1))
        return Statement("PLOTON", {"x": args[0], "y": args[1] if len(args) > 1 else "0"}, raw, line_no)

    # Line (draw between last two plots)
    if s.lower() == "line":
        return Statement("LINE", {}, raw, line_no)

    # F-Line x1,y1,x2,y2
    m = _FLINE_RE.match(s)
    if m:
        args = _split_args(m.group(1))
        if len(args) >= 4:
            return Statement("FLINE", {
                "x1": args[0], "y1": args[1], "x2": args[2], "y2": args[3],
            }, raw, line_no)

    # DrawStat
    if s.lower() == "drawstat":
        return Statement("DRAWSTAT", {}, raw, line_no)

    # Prog "name"
    m = _PROG_RE.match(s)
    if m:
        return Statement("PROG", {"name": m.group(1)}, raw, line_no)

    # Return
    if s.lower() == "return":
        return Statement("RETURN", {}, raw, line_no)

    # Stop
    if s.lower() == "stop":
        return Statement("STOP", {}, raw, line_no)

    # Getkey
    if s.lower() == "getkey":
        return Statement("GETKEY", {}, raw, line_no)

    # Dim List n
    m = _DIM_LIST_RE.match(s)
    if m:
        return Statement("DIM_LIST", {"n": m.group(1).strip()}, raw, line_no)

    # List n (bare access)
    m = _LIST_RE.match(s)
    if m:
        return Statement("LIST_ACCESS", {"n": m.group(1)}, raw, line_no)

    # Dsz — decrement variable, skip next stmt if result is zero
    m = _DSZ_RE.match(s)
    if m:
        return Statement("DSZ", {"var": m.group(1).upper()}, raw, line_no)

    # Isz — increment variable, skip next stmt if result is zero
    m = _ISZ_RE.match(s)
    if m:
        return Statement("ISZ", {"var": m.group(1).upper()}, raw, line_no)

    # Fill(value, Mat X) — zero-fill or fill a matrix with a constant
    m = _FILL_RE.match(s)
    if m:
        return Statement("FILL_MAT", {"expr": m.group(1).strip(), "mat": m.group(2).upper()}, raw, line_no)

    # Mode-setting and display commands with no arguments we can't execute —
    # silently ignore rather than treating as a syntax error expression.
    if _IGNORE_RE.match(s):
        return Statement("NOP", {}, raw, line_no)

    # Default: evaluate as an expression (display the result)
    return Statement("EXPR", {"expr": s}, raw, line_no)


def _expand_implies(line: str) -> list[str]:
    """Expand  cond⇒stmt  (or chained  c1⇒c2⇒stmt) into If/Then/IfEnd lines.

    Chained form  c1⇒c2⇒stmt  is treated as  (c1 And c2)⇒stmt.
    The ⇒ operator comes from CAT files and is Casio's single-line conditional.
    """
    if '⇒' not in line:
        return [line]
    parts = [p.strip() for p in line.split('⇒')]
    # Last part is the action; all preceding parts are conditions
    *conds, stmt = parts
    conds = [c for c in conds if c]
    if not conds or not stmt:
        return [line]
    if len(conds) == 1:
        cond = conds[0]
    else:
        cond = ' And '.join(f'({c})' for c in conds)
    return [f'If {cond}', 'Then', stmt, 'IfEnd']


def parse_program(source: str) -> list[Statement]:
    """Parse a Casio BASIC source string into a list of Statements."""
    stmts: list[Statement] = []
    for line_no, raw_line in enumerate(source.splitlines(), 1):
        raw_line = re.sub(r"\s*//.*$", "", raw_line).strip()   # strip // comments
        raw_line = _normalise(raw_line)
        if not raw_line:
            continue
        # Expand ⇒ operator before colon-splitting (CAT format conditional)
        for line in _expand_implies(raw_line):
            for part in _split_colon(line):
                if part:
                    stmts.append(parse_stmt(part, line_no))
    return stmts


# ── Jump-table builder ────────────────────────────────────────────────────────

def build_jump_table(stmts: list[Statement]) -> dict:
    """Pre-compute jump targets for all control-flow constructs."""
    jt: dict = {}

    # Labels
    for i, s in enumerate(stmts):
        if s.cmd == "LBL":
            jt[("LBL", s.args["label"])] = i

    # For/Next — stack-based for nesting
    for_stk: list[int] = []
    for i, s in enumerate(stmts):
        if s.cmd == "FOR":
            for_stk.append(i)
        elif s.cmd == "NEXT" and for_stk:
            fi = for_stk.pop()
            jt[("FOR_BODY", fi)] = fi + 1   # first statement of body
            jt[("FOR_EXIT", fi)] = i + 1    # statement after Next

    # While/WhileEnd
    while_stk: list[int] = []
    for i, s in enumerate(stmts):
        if s.cmd == "WHILE":
            while_stk.append(i)
        elif s.cmd == "WHILEEND" and while_stk:
            wi = while_stk.pop()
            jt[("WHILE_EXIT",   wi)] = i + 1   # statement after WhileEnd
            jt[("WHILEEND_TO",  i )] = wi       # jump back to While

    # Do/LpWhile
    do_stk: list[int] = []
    for i, s in enumerate(stmts):
        if s.cmd == "DO":
            do_stk.append(i)
        elif s.cmd == "LPWHILE" and do_stk:
            di = do_stk.pop()
            jt[("DO_BODY",    di)] = di + 1    # first statement of body
            jt[("LPWHILE_TO", i )] = di + 1   # loop-back (to body, not Do itself)

    # If/Else/IfEnd
    if_stk: list[dict] = []
    for i, s in enumerate(stmts):
        if s.cmd == "IF_BLOCK":
            if_stk.append({"if": i, "else": None})
        elif s.cmd == "ELSE" and if_stk:
            if_stk[-1]["else"] = i
        elif s.cmd == "IFEND" and if_stk:
            entry    = if_stk.pop()
            fi       = entry["if"]
            ei       = entry["else"]
            jt[("IF_IFEND",  fi)] = i          # jump here if cond false + no else
            jt[("IF_ELSE",   fi)] = ei          # else position (may be None)
            if ei is not None:
                jt[("ELSE_IFEND", ei)] = i      # Else jumps to IfEnd

    return jt


# ── Run result ────────────────────────────────────────────────────────────────

class RunResult:
    """Accumulated output from executing a Casio BASIC program."""

    def __init__(self) -> None:
        self.events: list[dict]  = []
        self.variables: dict     = {}
        self.matrices: dict      = {}
        self.error: str | None   = None
        self.terminated: bool    = False
        self.input_needed: bool  = False
        self.executing_prog: str = ""  # innermost program name when MAX_ITERATIONS hit

    # convenience helpers
    def text(self, t: str)                       -> None: self.events.append({"type": "text",     "text": t})
    def locate(self, x: int, y: int, t: str)    -> None: self.events.append({"type": "locate",   "x": x, "y": y, "text": t})
    def clrtext(self)                            -> None: self.events.append({"type": "clrtext"})
    def clrgraph(self)                           -> None: self.events.append({"type": "clrgraph"})
    def pause(self, t: str = "")                 -> None: self.events.append({"type": "pause",    "text": t})
    def plot(self, cmd: str, col: int, row: int) -> None: self.events.append({"type": "plot",     "cmd": cmd, "col": col, "row": row})
    def fline(self, x1, y1, x2, y2)             -> None: self.events.append({"type": "fline",    "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    def graph_y(self, expr: str)                 -> None: self.events.append({"type": "graph_y",  "expr": expr})
    def drawstat(self)                           -> None: self.events.append({"type": "drawstat"})


# ── Executor ──────────────────────────────────────────────────────────────────

class CasioBasicInterpreter:
    """Execute Casio BASIC programs."""

    def __init__(self, angle_mode: str = "DEG") -> None:
        self.angle_mode  = angle_mode
        self.variables: dict = {c: 0.0 for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
        self.variables["ANS"] = 0.0
        self.variables["θ"] = 0.0   # theta — extra Casio variable
        self.variables["r"] = 0.0   # r — polar coordinate variable
        self.lists: dict[int, list] = {}
        self.matrices: dict[str, list[list[float]]] = {}  # "A"…"F" → 2-D list
        self.view: dict = {
            "xmin": -6.3, "xmax": 6.3, "xscl": 1.0,
            "ymin": -3.1, "ymax": 3.1, "yscl": 1.0,
        }
        self.programs: dict[str, str] = {}  # name → source for Prog "name"
        self._current_key: int = 0           # Casio key code for Getkey

    # ── Convenience evaluation wrappers ─────────────────────────────────────

    def _ev(self, expr: str) -> float:
        """Evaluate expression with current interpreter state (vars + matrices)."""
        return _eval(expr, self.variables, self.angle_mode, self.matrices, self._current_key)

    def _evc(self, cond: str) -> bool:
        """Evaluate condition with current interpreter state (vars + matrices)."""
        return _eval_cond(cond, self.variables, self.angle_mode, self.matrices, self._current_key)

    # ── Public entry point ───────────────────────────────────────────────────

    def run(
        self,
        source: str,
        inputs: list | None = None,
        *,
        key: int = 0,
        start_label: str | None = None,
        state_variables: dict | None = None,
        state_matrices: dict | None = None,
        prog_name: str = "main",
    ) -> RunResult:
        """Execute *source* to completion.

        *inputs*         — pre-supplied Input values (batch / testing).
        *key*            — Casio Getkey code active for this execution frame.
        *start_label*    — if given, jump to this Lbl before starting.
        *state_variables*— restore these variable values before running.
        *state_matrices* — restore these matrices before running.
        *prog_name*      — name used in executing_prog tracking.
        """
        self._current_key = key

        # Restore game state from a previous frame
        if state_variables:
            for k, v in state_variables.items():
                if isinstance(v, (int, float)):
                    self.variables[k] = float(v)
        if state_matrices:
            for k, v in state_matrices.items():
                if isinstance(v, list):
                    self.matrices[k] = v

        stmts = parse_program(source)
        jt    = build_jump_table(stmts)
        res   = RunResult()
        inp   = list(inputs or [])

        # Find start_ip from label name
        start_ip = 0
        if start_label:
            for i, s in enumerate(stmts):
                if s.cmd == "LBL" and s.args.get("label", "").upper() == start_label.upper():
                    start_ip = i + 1
                    break

        self._execute(stmts, jt, res, inp, call_depth=0, start_ip=start_ip, program_name=prog_name)
        res.variables = dict(self.variables)
        res.matrices  = {k: v for k, v in self.matrices.items()}
        return res

    # ── Core execution loop ──────────────────────────────────────────────────

    def _execute(
        self,
        stmts: list[Statement],
        jt:    dict,
        res:   RunResult,
        inp:   list,
        call_depth: int,
        start_ip: int = 0,
        program_name: str = "main",
    ) -> None:
        if call_depth > MAX_CALL_DEPTH:
            res.error = "Stack ERROR"
            return

        ip          = start_ip
        inp_pos     = 0
        loop_stk:   list[dict] = []
        iterations  = 0

        while ip < len(stmts):
            iterations += 1
            if iterations > MAX_ITERATIONS:
                res.terminated = True
                res.error = "Terminated"
                res.executing_prog = program_name
                return
            if res.error or res.terminated:
                return

            s = stmts[ip]

            # ── Assignment  expr→VAR ─────────────────────────────────────
            if s.cmd == "ASSIGN":
                try:
                    v = self._ev(s.args["expr"])
                    self.variables[s.args["var"]] = v
                    self.variables["ANS"] = v
                except ValueError as e:
                    res.error = str(e)
                    return
                ip += 1

            # ── Matrix element assignment  expr→Mat X[r,c] ───────────────
            elif s.cmd == "MAT_ASSIGN":
                try:
                    val  = self._ev(s.args["expr"])
                    r    = int(round(self._ev(s.args["row"])))
                    c    = int(round(self._ev(s.args["col"])))
                    name = s.args["mat"]
                    if name not in self.matrices:
                        self.matrices[name] = [[0.0] * 30 for _ in range(10)]
                    mat = self.matrices[name]
                    # Grow matrix if needed
                    while len(mat) < r:
                        mat.append([0.0] * len(mat[0]))
                    while len(mat[0]) < c:
                        for row in mat:
                            row.append(0.0)
                    mat[r - 1][c - 1] = val
                except (ValueError, IndexError):
                    pass
                ip += 1

            # ── Fill matrix ───────────────────────────────────────────────
            elif s.cmd == "FILL_MAT":
                try:
                    val  = self._ev(s.args["expr"])
                    name = s.args["mat"]
                    if name in self.matrices:
                        mat = self.matrices[name]
                        for row in mat:
                            for ci in range(len(row)):
                                row[ci] = val
                    # If matrix doesn't exist, nothing to fill
                except ValueError:
                    pass
                ip += 1

            # ── Bare expression ──────────────────────────────────────────
            elif s.cmd == "EXPR":
                try:
                    v = self._ev(s.args["expr"])
                    self.variables["ANS"] = v
                    res.text(_fmt(v))
                except ValueError:
                    pass   # silently ignore unevaluable bare expressions
                ip += 1

            # ── Print string literal ─────────────────────────────────────
            elif s.cmd == "PRINT_STR":
                res.text(s.args["text"])
                ip += 1

            elif s.cmd == "PRINT_PAUSE":
                res.text(s.args["text"])
                res.pause()
                ip += 1

            # ── Print expression ─────────────────────────────────────────
            elif s.cmd == "PRINT_EXPR":
                expr = s.args["expr"]
                if expr.startswith('"') and expr.endswith('"'):
                    res.text(expr[1:-1])
                else:
                    try:
                        v = self._ev(expr)
                        self.variables["ANS"] = v
                        res.text(_fmt(v))
                    except ValueError as e:
                        res.text(str(e))
                ip += 1

            # ── Pause ◢ ─────────────────────────────────────────────────
            elif s.cmd == "PAUSE":
                res.pause()
                ip += 1

            # ── Input ────────────────────────────────────────────────────
            elif s.cmd == "INPUT":
                if inp_pos < len(inp):
                    raw = inp[inp_pos]
                    inp_pos += 1
                    try:
                        v = float(raw)
                    except (TypeError, ValueError):
                        try:
                            v = self._ev(str(raw))
                        except ValueError:
                            res.error = "Input ERROR"
                            return
                    self.variables[s.args["var"]] = v
                    self.variables["ANS"] = v
                else:
                    # No queued input — default to 0 and continue (batch mode).
                    # Emit an input event so the frontend can show the prompt.
                    res.input_needed = True
                    res.events.append({
                        "type":   "input",
                        "prompt": s.args.get("prompt", "?"),
                        "var":    s.args["var"],
                    })
                    self.variables[s.args["var"]] = 0.0
                    self.variables["ANS"] = 0.0
                ip += 1

            # ── Locate ───────────────────────────────────────────────────
            elif s.cmd == "LOCATE":
                try:
                    x   = int(self._ev(s.args["x"]))
                    y   = int(self._ev(s.args["y"]))
                    txt = s.args["text"]
                    if txt.startswith('"') and txt.endswith('"'):
                        txt = txt[1:-1]
                    else:
                        txt = _fmt(self._ev(txt))
                    res.locate(x, y, txt)
                except ValueError as e:
                    res.error = str(e)
                    return
                ip += 1

            # ── ClrText / ClrGraph / ClrList ─────────────────────────────
            elif s.cmd == "CLRTEXT":
                res.clrtext()
                ip += 1

            elif s.cmd == "CLRGRAPH":
                res.clrgraph()
                ip += 1

            elif s.cmd == "CLRLIST":
                self.lists.clear()
                ip += 1

            # ── For loop ─────────────────────────────────────────────────
            elif s.cmd == "FOR":
                try:
                    var   = s.args["var"]
                    start = self._ev(s.args["start"])
                    end   = self._ev(s.args["end"])
                    step  = self._ev(s.args["step"])
                    if step == 0:
                        res.error = "Math ERROR"
                        return
                    self.variables[var] = start
                    skip = (step > 0 and start > end) or (step < 0 and start < end)
                    if skip:
                        exit_ip = jt.get(("FOR_EXIT", ip))
                        ip = exit_ip if exit_ip is not None else ip + 1
                    else:
                        loop_stk.append({"type": "FOR", "var": var,
                                          "end": end, "step": step, "for_ip": ip})
                        ip += 1
                except ValueError as e:
                    res.error = str(e)
                    return

            elif s.cmd == "NEXT":
                if loop_stk and loop_stk[-1]["type"] == "FOR":
                    ls  = loop_stk[-1]
                    nv  = self.variables[ls["var"]] + ls["step"]
                    self.variables[ls["var"]] = nv
                    cont = (ls["step"] > 0 and nv <= ls["end"]) or \
                           (ls["step"] < 0 and nv >= ls["end"])
                    if cont:
                        ip = jt.get(("FOR_BODY", ls["for_ip"]), ls["for_ip"] + 1)
                    else:
                        loop_stk.pop()
                        ip += 1
                else:
                    ip += 1

            # ── While loop ───────────────────────────────────────────────
            elif s.cmd == "WHILE":
                try:
                    if self._evc(s.args["cond"]):
                        loop_stk.append({"type": "WHILE", "while_ip": ip})
                        ip += 1
                    else:
                        exit_ip = jt.get(("WHILE_EXIT", ip))
                        ip = exit_ip if exit_ip is not None else ip + 1
                except ValueError as e:
                    res.error = str(e)
                    return

            elif s.cmd == "WHILEEND":
                if loop_stk and loop_stk[-1]["type"] == "WHILE":
                    ip = loop_stk[-1]["while_ip"]   # re-evaluate the While condition
                else:
                    ip += 1

            # ── Do / LpWhile ─────────────────────────────────────────────
            elif s.cmd == "DO":
                loop_stk.append({"type": "DO", "body_ip": ip + 1})
                ip += 1

            elif s.cmd == "LPWHILE":
                try:
                    cont = self._evc(s.args["cond"])
                    if cont and loop_stk and loop_stk[-1]["type"] == "DO":
                        ip = loop_stk[-1]["body_ip"]
                    else:
                        if loop_stk and loop_stk[-1]["type"] == "DO":
                            loop_stk.pop()
                        ip += 1
                except ValueError as e:
                    res.error = str(e)
                    return

            # ── Break (exit innermost loop) ───────────────────────────────
            elif s.cmd == "BREAK":
                # Pop the innermost loop and jump past it
                exited = False
                while loop_stk:
                    top = loop_stk.pop()
                    if top["type"] == "FOR":
                        exit_ip = jt.get(("FOR_EXIT", top["for_ip"]))
                        if exit_ip is not None:
                            ip = exit_ip
                            exited = True
                            break
                    elif top["type"] == "WHILE":
                        exit_ip = jt.get(("WHILE_EXIT", top["while_ip"]))
                        if exit_ip is not None:
                            ip = exit_ip
                            exited = True
                            break
                    elif top["type"] == "DO":
                        # Find the LpWhile and jump past it
                        for bi in range(ip, len(stmts)):
                            if stmts[bi].cmd == "LPWHILE":
                                ip = bi + 1
                                exited = True
                                break
                        if exited:
                            break
                if not exited:
                    ip += 1

            # ── If block ─────────────────────────────────────────────────
            elif s.cmd == "IF_BLOCK":
                try:
                    cond_val = self._evc(s.args["cond"])
                    if cond_val:
                        ip += 1
                    else:
                        ei = jt.get(("IF_ELSE",  ip))
                        fi = jt.get(("IF_IFEND", ip))
                        if ei is not None:
                            ip = ei + 1        # jump into else block
                        elif fi is not None:
                            ip = fi + 1        # jump past IfEnd
                        else:
                            ip += 1
                except ValueError as e:
                    res.error = str(e)
                    return

            elif s.cmd == "THEN":
                ip += 1

            elif s.cmd == "ELSE":
                # We were in the then-block; jump to IfEnd
                fi = jt.get(("ELSE_IFEND", ip))
                ip = (fi + 1) if fi is not None else ip + 1

            elif s.cmd == "IFEND":
                ip += 1

            # ── Inline If ────────────────────────────────────────────────
            elif s.cmd == "IF_INLINE":
                try:
                    if self._evc(s.args["cond"]):
                        jumped = self._exec_inline(s.args["then_stmt"], res, jt, stmts)
                        if res.error or res.terminated:
                            return
                        if jumped is not None:
                            ip = jumped
                            continue
                except ValueError as e:
                    res.error = str(e)
                    return
                ip += 1

            # ── Lbl / Goto ───────────────────────────────────────────────
            elif s.cmd == "LBL":
                ip += 1

            elif s.cmd == "GOTO":
                target = jt.get(("LBL", s.args["label"]))
                if target is not None:
                    ip = target
                else:
                    res.error = f"Goto {s.args['label']}: label not found"
                    return

            # ── ViewWindow ───────────────────────────────────────────────
            elif s.cmd == "VIEWWINDOW":
                keys = ("xmin", "xmax", "xscl", "ymin", "ymax", "yscl")
                try:
                    for k, v in zip(keys, s.args["args"]):
                        self.view[k] = self._ev(v)
                except ValueError as e:
                    res.error = str(e)
                    return
                ip += 1

            # ── Graph Y= ─────────────────────────────────────────────────
            elif s.cmd == "GRAPH_Y":
                res.graph_y(s.args["expr"])
                ip += 1

            # ── PlotOn / PlotOff / PlotChg ───────────────────────────────
            elif s.cmd in ("PLOTON", "PLOTOFF", "PLOTCHG"):
                try:
                    px  = self._ev(s.args["x"])
                    py  = self._ev(s.args["y"])
                    col = int((px - self.view["xmin"]) /
                              (self.view["xmax"] - self.view["xmin"]) * 127)
                    row = int((self.view["ymax"] - py) /
                              (self.view["ymax"] - self.view["ymin"]) * 63)
                    col = max(0, min(127, col))
                    row = max(0, min(63,  row))
                    res.plot(s.cmd, col, row)
                except ValueError:
                    pass
                ip += 1

            # ── Line ─────────────────────────────────────────────────────
            elif s.cmd == "LINE":
                res.events.append({"type": "line"})
                ip += 1

            # ── F-Line ───────────────────────────────────────────────────
            elif s.cmd == "FLINE":
                try:
                    x1 = self._ev(s.args["x1"])
                    y1 = self._ev(s.args["y1"])
                    x2 = self._ev(s.args["x2"])
                    y2 = self._ev(s.args["y2"])
                    res.fline(x1, y1, x2, y2)
                except ValueError:
                    pass
                ip += 1

            # ── DrawStat ─────────────────────────────────────────────────
            elif s.cmd == "DRAWSTAT":
                res.drawstat()
                ip += 1

            # ── Prog (subroutine) ─────────────────────────────────────────
            elif s.cmd == "PROG":
                name = s.args["name"]
                if name not in self.programs:
                    res.error = f'Program "{name}" not found'
                    return
                sub_stmts = parse_program(self.programs[name])
                sub_jt    = build_jump_table(sub_stmts)
                self._execute(sub_stmts, sub_jt, res, inp[inp_pos:], call_depth + 1,
                               program_name=name)
                if res.error or res.terminated:
                    return
                ip += 1

            # ── Return / Stop ────────────────────────────────────────────
            elif s.cmd == "RETURN":
                return   # unwind call stack

            elif s.cmd == "STOP":
                res.terminated = True
                return

            # ── Dsz / Isz ────────────────────────────────────────────────
            elif s.cmd == "DSZ":
                v = s.args["var"]
                self.variables[v] = self.variables.get(v, 0) - 1
                ip = ip + 2 if self.variables[v] == 0 else ip + 1

            elif s.cmd == "ISZ":
                v = s.args["var"]
                self.variables[v] = self.variables.get(v, 0) + 1
                ip = ip + 2 if self.variables[v] == 0 else ip + 1

            # ── NOP (AxesOff, GridOff, colour commands, etc.) ────────────
            elif s.cmd == "NOP":
                ip += 1

            # ── Getkey ───────────────────────────────────────────────────
            elif s.cmd == "GETKEY":
                self.variables["ANS"] = float(self._current_key)
                ip += 1

            # ── Dim List / List access ────────────────────────────────────
            elif s.cmd == "DIM_LIST":
                try:
                    n = int(self._ev(s.args["n"]))
                    if n not in self.lists:
                        self.lists[n] = []
                except ValueError:
                    pass
                ip += 1

            elif s.cmd == "LIST_ACCESS":
                n = int(s.args["n"])
                res.text(str(self.lists.get(n, [])))
                ip += 1

            else:
                ip += 1   # unknown / unimplemented — skip

    # ── Inline single-statement executor ─────────────────────────────────────

    def _exec_inline(
        self,
        s:     Statement,
        res:   RunResult,
        jt:    dict,
        stmts: list[Statement],
    ) -> int | None:
        """Execute one statement that appeared inline after 'Then'.

        Returns a new ip if the statement caused a jump (Goto), else None.
        """
        if s.cmd == "ASSIGN":
            try:
                v = self._ev(s.args["expr"])
                self.variables[s.args["var"]] = v
                self.variables["ANS"] = v
            except ValueError as e:
                res.error = str(e)
        elif s.cmd == "MAT_ASSIGN":
            try:
                val  = self._ev(s.args["expr"])
                r    = int(round(self._ev(s.args["row"])))
                c    = int(round(self._ev(s.args["col"])))
                name = s.args["mat"]
                if name not in self.matrices:
                    self.matrices[name] = [[0.0] * 30 for _ in range(10)]
                mat = self.matrices[name]
                while len(mat) < r:
                    mat.append([0.0] * len(mat[0]))
                while len(mat[0]) < c:
                    for row in mat:
                        row.append(0.0)
                mat[r - 1][c - 1] = val
            except (ValueError, IndexError):
                pass
        elif s.cmd == "PRINT_STR":
            res.text(s.args["text"])
        elif s.cmd in ("PRINT_EXPR", "EXPR"):
            expr = s.args.get("expr", "")
            if expr.startswith('"') and expr.endswith('"'):
                res.text(expr[1:-1])
            else:
                try:
                    v = self._ev(expr)
                    self.variables["ANS"] = v
                    res.text(_fmt(v))
                except ValueError:
                    pass
        elif s.cmd == "LOCATE":
            try:
                x   = int(self._ev(s.args["x"]))
                y   = int(self._ev(s.args["y"]))
                txt = s.args["text"]
                if txt.startswith('"') and txt.endswith('"'):
                    txt = txt[1:-1]
                else:
                    txt = _fmt(self._ev(txt))
                res.locate(x, y, txt)
            except ValueError:
                pass
        elif s.cmd == "DSZ":
            v = s.args["var"]
            self.variables[v] = self.variables.get(v, 0) - 1
        elif s.cmd == "ISZ":
            v = s.args["var"]
            self.variables[v] = self.variables.get(v, 0) + 1
        elif s.cmd == "PROG":
            name = s.args["name"]
            if name in self.programs:
                sub_stmts = parse_program(self.programs[name])
                sub_jt    = build_jump_table(sub_stmts)
                self._execute(sub_stmts, sub_jt, res, [], 1, program_name=name)
        elif s.cmd == "GOTO":
            target = jt.get(("LBL", s.args["label"]))
            if target is not None:
                return target
            res.error = f"Goto {s.args['label']}: label not found"
        elif s.cmd == "STOP":
            res.terminated = True
        elif s.cmd == "RETURN":
            res.terminated = True   # treat as stop in inline context
        # Other commands (nested If, loops, NOP) — skip silently
        return None
