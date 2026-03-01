"""TABLE mode for the Casio CFX-9850G emulator.

Generates a value table for F(X) over [start, end] with a given step.
"""

from __future__ import annotations
import sympy as sp
from app.calculator.engine import CalculatorEngine, _make_trig_local, _TRANSFORMATIONS
from sympy.parsing.sympy_parser import parse_expr


MAX_ROWS = 500   # safety cap


class TableMode:
    def __init__(self, engine: CalculatorEngine):
        self.engine = engine
        self.function: str = ""
        self.start: float = 1.0
        self.end: float = 5.0
        self.step: float = 1.0

    def set_function(self, expr: str) -> None:
        self.function = expr.strip()

    def set_range(self, start: float, end: float, step: float) -> None:
        self.start = float(start)
        self.end = float(end)
        self.step = float(step)

    def generate(self) -> dict:
        """Return {"rows": [{x, y}, ...], "error": str|None}."""
        if not self.function:
            return {"rows": [], "error": "No function defined"}

        if self.step == 0:
            return {"rows": [], "error": "Step cannot be zero"}

        if self.step > 0 and self.start > self.end:
            return {"rows": [], "error": "Start > End with positive step"}

        if self.step < 0 and self.start < self.end:
            return {"rows": [], "error": "Start < End with negative step"}

        local_dict = _make_trig_local(self.engine.angle_mode, self.engine.memory)
        x_sym = sp.Symbol("X")
        local_dict["X"] = x_sym

        try:
            sym_expr = parse_expr(
                self.function,
                local_dict=local_dict,
                transformations=_TRANSFORMATIONS,
            )
        except Exception:
            return {"rows": [], "error": "Syntax ERROR"}

        rows = []
        x = self.start
        count = 0

        while True:
            if self.step > 0 and x > self.end + 1e-10:
                break
            if self.step < 0 and x < self.end - 1e-10:
                break
            if count >= MAX_ROWS:
                break

            try:
                y_sym = sym_expr.subs(x_sym, sp.Float(x)).evalf(12)
                y_complex = complex(y_sym)
                if abs(y_complex.imag) > 1e-9:
                    y_str = "Non-Real"
                elif abs(y_complex.real) > 9.99e99:
                    y_str = "Math ERROR"
                else:
                    yr = y_complex.real
                    if abs(yr - round(yr)) < 1e-9 and abs(yr) < 1e15:
                        y_str = str(int(round(yr)))
                    else:
                        y_str = f"{yr:.10g}"
            except Exception:
                y_str = "Math ERROR"

            rows.append({
                "x": f"{x:.10g}" if abs(x - round(x)) > 1e-9 else str(int(round(x))),
                "y": y_str,
            })

            x = round(x + self.step, 10)   # avoid float drift
            count += 1

        return {"rows": rows, "error": None}
