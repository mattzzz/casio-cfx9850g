"""SymPy-based expression evaluator for the Casio CFX-9850G emulator.

Rules (from CLAUDE.md):
- Never use eval() — use SymPy parse_expr() only
- Default angle mode: DEG
- Division by zero → "Math ERROR"
- Overflow (|x| > 9.99e99) → "Math ERROR"
- Complex output format: a+bi  (not Python's a+bj)
- Max 10 significant figures
"""

from __future__ import annotations

import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

from app.calculator.memory import MemoryStore

_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

_OVERFLOW = sp.Float("9.99e99")

# ── angle-aware trig helpers ─────────────────────────────────────────────────

def _make_trig_local(angle_mode: str, memory: MemoryStore) -> dict:
    """Build local_dict for parse_expr with angle-aware trig functions."""

    if angle_mode == "DEG":
        k = sp.pi / 180
        rk = 180 / sp.pi
    elif angle_mode == "GRD":
        k = sp.pi / 200
        rk = 200 / sp.pi
    else:  # RAD
        k = sp.Integer(1)
        rk = sp.Integer(1)

    def sin_fn(x):   return sp.sin(x * k)
    def cos_fn(x):   return sp.cos(x * k)
    def tan_fn(x):   return sp.tan(x * k)
    def asin_fn(x):  return sp.asin(x) * rk
    def acos_fn(x):  return sp.acos(x) * rk
    def atan_fn(x):  return sp.atan(x) * rk
    def atan2_fn(y, x): return sp.atan2(y, x) * rk

    local: dict = {
        # trig
        "sin": sin_fn, "cos": cos_fn, "tan": tan_fn,
        "asin": asin_fn, "acos": acos_fn, "atan": atan_fn,
        "Asin": asin_fn, "Acos": acos_fn, "Atan": atan_fn,
        # log/exp  (Casio 'log' = log base 10)
        "log": lambda x: sp.log(x, 10),
        "ln": sp.log,
        "exp": sp.exp,
        # roots / powers
        "sqrt": sp.sqrt,
        "Abs": sp.Abs, "abs": sp.Abs,
        # constants — lowercase only; uppercase E is the variable
        "pi": sp.pi,
        "e": sp.E,
        "i": sp.I,
    }

    # Variables A–Z + Ans from memory (added after constants so they
    # can override uppercase letters like E, but 'e' stays Euler's number)
    local.update(memory.as_sympy_dict())
    return local


# ── result formatter ─────────────────────────────────────────────────────────

def _format(value: sp.Basic) -> str:
    """Format a SymPy result as the CFX-9850G would display it."""

    # Infinities / zoo → Math ERROR
    if value in (sp.zoo, sp.oo, sp.nan, -sp.oo):
        return "Math ERROR"

    # Numerically evaluate to a complex float
    try:
        numeric = complex(value.evalf(15))
    except Exception:
        return "Math ERROR"

    re_part = numeric.real
    im_part = numeric.imag

    # Overflow check
    if abs(re_part) > 9.99e99 or abs(im_part) > 9.99e99:
        return "Math ERROR"

    def _fmt_float(x: float) -> str:
        """Format a single real number to ≤10 significant figures."""
        if x == 0.0:
            return "0"
        # Check if result is (very close to) an integer
        if abs(x - round(x)) < 1e-9 and abs(x) < 1e15:
            return str(int(round(x)))
        # Use g format for up to 10 sig figs
        formatted = f"{x:.10g}"
        return formatted

    if abs(im_part) < 1e-10:
        return _fmt_float(re_part)

    # Complex result: a+bi or a-bi
    re_str = _fmt_float(re_part) if abs(re_part) > 1e-10 else ""
    im_abs = abs(im_part)
    im_str = _fmt_float(im_abs) if abs(im_abs - 1) > 1e-10 else ""
    sign = "+" if im_part > 0 else "-"

    if re_str:
        return f"{re_str}{sign}{im_str}i"
    else:
        return f"{sign if im_part < 0 else ''}{im_str}i"


# ── public evaluator ─────────────────────────────────────────────────────────

class CalculatorEngine:
    def __init__(self):
        self.angle_mode: str = "DEG"   # DEG | RAD | GRD
        self.memory: MemoryStore = MemoryStore()

    def evaluate(self, expression: str) -> str:
        """Evaluate an expression string. Returns a formatted result or error string."""
        expr = expression.strip()
        if not expr:
            return ""

        local_dict = _make_trig_local(self.angle_mode, self.memory)

        try:
            result = parse_expr(
                expr,
                local_dict=local_dict,
                transformations=_TRANSFORMATIONS,
            )
        except (SyntaxError, TypeError, AttributeError, ValueError):
            return "Syntax ERROR"
        except Exception:
            return "Syntax ERROR"

        # Simplify / evaluate numerically
        try:
            result = result.evalf(15)
        except Exception:
            return "Math ERROR"

        formatted = _format(result)

        # Store in Ans if valid result
        if "ERROR" not in formatted:
            try:
                self.memory.set_ans(result)
            except Exception:
                pass

        return formatted

    def store_variable(self, name: str, value_expr: str) -> str:
        """Evaluate value_expr and store in variable name (A–Z)."""
        result_str = self.evaluate(value_expr)
        if "ERROR" in result_str:
            return result_str
        # Re-evaluate to get the SymPy value
        local_dict = _make_trig_local(self.angle_mode, self.memory)
        try:
            sym_val = parse_expr(
                value_expr,
                local_dict=local_dict,
                transformations=_TRANSFORMATIONS,
            ).evalf(15)
            self.memory.set(name, sym_val)
        except Exception:
            return "Math ERROR"
        return result_str

    def set_angle_mode(self, mode: str) -> None:
        if mode in ("DEG", "RAD", "GRD"):
            self.angle_mode = mode
