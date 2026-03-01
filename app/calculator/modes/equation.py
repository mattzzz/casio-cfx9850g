"""EQUA mode for Casio CFX-9850G emulator.

Supports:
  - Polynomial equations of degree 2–6
    Coefficients supplied highest-degree first (matching CFX-9850G input).
  - Simultaneous linear equations: 2–6 unknowns
    Coefficient matrix + constant vector → solution.
"""

from __future__ import annotations

import numpy as np


def _fmt(x: float) -> str:
    """Format a float to ≤10 sig figs."""
    if abs(x) < 1e-10:
        return "0"
    if abs(x - round(x)) < 1e-9 and abs(x) < 1e15:
        return str(int(round(x)))
    return f"{x:.10g}"


def _fmt_complex(re: float, im: float) -> str:
    """Format a complex root as 'a+bi' or 'a-bi'."""
    re_str = _fmt(re) if abs(re) > 1e-10 else ""
    im_abs = abs(im)
    im_str = "" if abs(im_abs - 1.0) < 1e-10 else _fmt(im_abs)
    sign = "+" if im > 0 else "-"
    if re_str:
        return f"{re_str}{sign}{im_str}i"
    return f"{'-' if im < 0 else ''}{im_str}i"


class EquationMode:
    """Casio CFX-9850G EQUA mode."""

    # ── Polynomial solver ─────────────────────────────────────────────────

    def polynomial(self, coefficients: list[float]) -> dict:
        """Solve a_n·xⁿ + … + a_1·x + a_0 = 0.

        coefficients: [a_n, a_{n-1}, …, a_1, a_0]
                      (highest-degree first, as entered on the CFX-9850G)
        Degree must be 2–6.
        Returns: {"roots": [...], "degree": n}
        """
        n = len(coefficients) - 1
        if not (2 <= n <= 6):
            return {"error": "Argument ERROR"}
        if coefficients[0] == 0:
            return {"error": "Argument ERROR"}

        try:
            roots_np = np.roots(coefficients)
            roots = []
            for r in roots_np:
                re = float(r.real)
                im = float(r.imag)
                if abs(im) < 1e-10:
                    roots.append(_fmt(re))
                else:
                    roots.append(_fmt_complex(re, im))
            return {"roots": roots, "degree": n}
        except Exception:
            return {"error": "Math ERROR"}

    # ── Simultaneous linear equations ─────────────────────────────────────

    def simultaneous(
        self,
        matrix: list[list[float]],
        constants: list[float],
    ) -> dict:
        """Solve the system  A·x = b.

        matrix:    n×n coefficient matrix (list of lists of float)
        constants: list of n right-hand-side values
        Returns:   {"solution": [x1, x2, …, xn]}
        """
        n = len(constants)
        if not (2 <= n <= 6):
            return {"error": "Argument ERROR"}
        if len(matrix) != n or any(len(row) != n for row in matrix):
            return {"error": "Argument ERROR"}

        try:
            A = np.array(matrix, dtype=float)
            b = np.array(constants, dtype=float)

            det = float(np.linalg.det(A))
            if abs(det) < 1e-12:
                # Check whether the system is consistent
                aug = np.column_stack([A, b])
                rank_a = np.linalg.matrix_rank(A)
                rank_aug = np.linalg.matrix_rank(aug)
                if rank_a == rank_aug:
                    return {"error": "Infinite Solutions"}
                else:
                    return {"error": "No Solution"}

            x = np.linalg.solve(A, b)
            return {"solution": [_fmt(float(xi)) for xi in x]}
        except np.linalg.LinAlgError:
            return {"error": "Math ERROR"}
