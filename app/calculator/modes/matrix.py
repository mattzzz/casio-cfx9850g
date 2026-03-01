"""MAT mode for Casio CFX-9850G emulator.

Matrices are labelled A–F.
Operations: define, add, subtract, multiply, transpose, determinant,
            inverse, RREF (row-reduced echelon form), scalar multiply.

Indices are 1-based in the public API (matching CFX-9850G) but
0-based internally.
"""

from __future__ import annotations

from typing import Optional

import numpy as np


def _fmt(x: float) -> str:
    """Format a float to ≤10 sig figs."""
    if abs(x) < 1e-10:
        return "0"
    if abs(x - round(x)) < 1e-9 and abs(x) < 1e15:
        return str(int(round(x)))
    return f"{x:.10g}"


def _mat_result(mat: np.ndarray) -> dict:
    """Convert numpy array to serialisable result dict."""
    result = mat.tolist()
    return {"matrix": [[_fmt(float(v)) for v in row] for row in result]}


class MatrixMode:
    """Casio CFX-9850G MAT mode — holds matrices A–F."""

    VALID_NAMES: frozenset[str] = frozenset("ABCDEF")

    def __init__(self) -> None:
        # Stored as list-of-lists of float, or None if undefined
        self._matrices: dict[str, Optional[list[list[float]]]] = {
            name: None for name in self.VALID_NAMES
        }

    # ── Define / query ────────────────────────────────────────────────────

    def define(self, name: str, rows: list[list[float]]) -> dict:
        """Define matrix <name> with given row data."""
        name = name.upper()
        if name not in self.VALID_NAMES:
            return {"error": "Argument ERROR"}
        if not rows:
            return {"error": "Argument ERROR"}
        ncols = len(rows[0])
        if ncols == 0 or any(len(r) != ncols for r in rows):
            return {"error": "Argument ERROR"}
        self._matrices[name] = [list(r) for r in rows]
        return {"name": name, "rows": len(rows), "cols": ncols}

    def get(self, name: str) -> Optional[list[list[float]]]:
        """Return raw matrix data or None."""
        return self._matrices.get(name.upper())

    def dimensions(self, name: str) -> dict:
        """Return {rows, cols} for a named matrix, or error."""
        m = self._matrices.get(name.upper())
        if m is None:
            return {"error": "Argument ERROR"}
        return {"rows": len(m), "cols": len(m[0])}

    # ── Element access (1-based row/col) ──────────────────────────────────

    def get_element(self, name: str, row: int, col: int) -> dict:
        m = self._matrices.get(name.upper())
        if m is None:
            return {"error": "Argument ERROR"}
        if not (1 <= row <= len(m) and 1 <= col <= len(m[0])):
            return {"error": "Argument ERROR"}
        return {"value": _fmt(m[row - 1][col - 1])}

    def set_element(self, name: str, row: int, col: int, value: float) -> dict:
        m = self._matrices.get(name.upper())
        if m is None:
            return {"error": "Argument ERROR"}
        if not (1 <= row <= len(m) and 1 <= col <= len(m[0])):
            return {"error": "Argument ERROR"}
        m[row - 1][col - 1] = float(value)
        return {"ok": True}

    # ── Arithmetic ────────────────────────────────────────────────────────

    def add(self, a: str, b: str) -> dict:
        ma, mb = self._get_np(a), self._get_np(b)
        if ma is None or mb is None:
            return {"error": "Argument ERROR"}
        if ma.shape != mb.shape:
            return {"error": "Dimension ERROR"}
        return _mat_result(ma + mb)

    def subtract(self, a: str, b: str) -> dict:
        ma, mb = self._get_np(a), self._get_np(b)
        if ma is None or mb is None:
            return {"error": "Argument ERROR"}
        if ma.shape != mb.shape:
            return {"error": "Dimension ERROR"}
        return _mat_result(ma - mb)

    def multiply(self, a: str, b: str) -> dict:
        ma, mb = self._get_np(a), self._get_np(b)
        if ma is None or mb is None:
            return {"error": "Argument ERROR"}
        if ma.shape[1] != mb.shape[0]:
            return {"error": "Dimension ERROR"}
        return _mat_result(ma @ mb)

    def scalar_multiply(self, scalar: float, a: str) -> dict:
        ma = self._get_np(a)
        if ma is None:
            return {"error": "Argument ERROR"}
        return _mat_result(scalar * ma)

    def transpose(self, a: str) -> dict:
        ma = self._get_np(a)
        if ma is None:
            return {"error": "Argument ERROR"}
        return _mat_result(ma.T)

    def determinant(self, a: str) -> dict:
        ma = self._get_np(a)
        if ma is None:
            return {"error": "Argument ERROR"}
        if ma.shape[0] != ma.shape[1]:
            return {"error": "Dimension ERROR"}
        try:
            det = float(np.linalg.det(ma))
            return {"result": _fmt(det)}
        except Exception:
            return {"error": "Math ERROR"}

    def inverse(self, a: str) -> dict:
        ma = self._get_np(a)
        if ma is None:
            return {"error": "Argument ERROR"}
        if ma.shape[0] != ma.shape[1]:
            return {"error": "Dimension ERROR"}
        try:
            inv = np.linalg.inv(ma)
            # Check for singular (inf values appear from near-singular matrices)
            if not np.all(np.isfinite(inv)):
                return {"error": "Singular Matrix"}
            return _mat_result(inv)
        except np.linalg.LinAlgError:
            return {"error": "Singular Matrix"}

    def rref(self, a: str) -> dict:
        """Row-reduced echelon form (uses SymPy for exact arithmetic)."""
        m = self._matrices.get(a.upper())
        if m is None:
            return {"error": "Argument ERROR"}
        try:
            import sympy as sp
            mat = sp.Matrix(m)
            rref_mat, _ = mat.rref()
            result = [
                [float(rref_mat[r, c]) for c in range(rref_mat.cols)]
                for r in range(rref_mat.rows)
            ]
            return {"matrix": [[_fmt(v) for v in row] for row in result]}
        except Exception:
            return {"error": "Math ERROR"}

    # ── Private helpers ───────────────────────────────────────────────────

    def _get_np(self, name: str) -> Optional[np.ndarray]:
        m = self._matrices.get(name.upper())
        if m is None:
            return None
        return np.array(m, dtype=float)
