"""STAT mode for Casio CFX-9850G emulator.

Supports:
  - 1-variable statistics: mean, Σx, Σx², σx (population), Sx (sample),
    n, minX, maxX, median
  - 2-variable statistics: means, sums, Σxy, σx/σy, Sx/Sy
  - Regression types: linear (y=a+bx), quadratic, logarithmic,
    exponential, power
"""

from __future__ import annotations

import math
from typing import Optional


def _fmt(x: float) -> str:
    """Format a float to ≤10 significant figures (CFX-9850G style)."""
    if x != x:  # NaN
        return "Math ERROR"
    if x == 0.0:
        return "0"
    if abs(x - round(x)) < 1e-9 and abs(x) < 1e15:
        return str(int(round(x)))
    return f"{x:.10g}"


class StatMode:
    """Casio CFX-9850G STAT mode computations."""

    # ── 1-variable statistics ─────────────────────────────────────────────

    def one_var(self, x_data: list[float]) -> dict:
        """Compute 1-variable statistics.

        Returns dict with: n, mean_x, sum_x, sum_x2, sigma_x, s_x,
                           min_x, max_x, median
        """
        n = len(x_data)
        if n == 0:
            return {"error": "Argument ERROR"}

        x_sum = sum(x_data)
        x_sum2 = sum(xi ** 2 for xi in x_data)
        mean_x = x_sum / n

        # Population std dev
        sigma_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x_data) / n)

        # Sample std dev (n-1) — undefined for n=1
        s_x = math.sqrt(
            sum((xi - mean_x) ** 2 for xi in x_data) / (n - 1)
        ) if n > 1 else 0.0

        sorted_data = sorted(x_data)
        if n % 2 == 0:
            median = (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2
        else:
            median = sorted_data[n // 2]

        return {
            "n": n,
            "mean_x": _fmt(mean_x),
            "sum_x": _fmt(x_sum),
            "sum_x2": _fmt(x_sum2),
            "sigma_x": _fmt(sigma_x),
            "s_x": _fmt(s_x),
            "min_x": _fmt(sorted_data[0]),
            "max_x": _fmt(sorted_data[-1]),
            "median": _fmt(median),
        }

    # ── 2-variable statistics ─────────────────────────────────────────────

    def two_var(self, x_data: list[float], y_data: list[float]) -> dict:
        """Compute 2-variable statistics."""
        n = len(x_data)
        if n != len(y_data):
            return {"error": "Argument ERROR"}
        if n == 0:
            return {"error": "Argument ERROR"}

        sum_x = sum(x_data)
        sum_y = sum(y_data)
        sum_x2 = sum(xi ** 2 for xi in x_data)
        sum_y2 = sum(yi ** 2 for yi in y_data)
        sum_xy = sum(xi * yi for xi, yi in zip(x_data, y_data))
        mean_x = sum_x / n
        mean_y = sum_y / n

        sigma_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x_data) / n)
        sigma_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y_data) / n)

        if n > 1:
            s_x = math.sqrt(
                sum((xi - mean_x) ** 2 for xi in x_data) / (n - 1)
            )
            s_y = math.sqrt(
                sum((yi - mean_y) ** 2 for yi in y_data) / (n - 1)
            )
        else:
            s_x = s_y = 0.0

        return {
            "n": n,
            "mean_x": _fmt(mean_x),
            "mean_y": _fmt(mean_y),
            "sum_x": _fmt(sum_x),
            "sum_y": _fmt(sum_y),
            "sum_x2": _fmt(sum_x2),
            "sum_y2": _fmt(sum_y2),
            "sum_xy": _fmt(sum_xy),
            "sigma_x": _fmt(sigma_x),
            "sigma_y": _fmt(sigma_y),
            "s_x": _fmt(s_x),
            "s_y": _fmt(s_y),
        }

    # ── Regression ────────────────────────────────────────────────────────

    def regression(
        self,
        x_data: list[float],
        y_data: list[float],
        reg_type: str = "linear",
    ) -> dict:
        """Compute regression coefficients.

        reg_type: 'linear' | 'quadratic' | 'logarithmic' |
                  'exponential' | 'power'

        Returns dict with 'a', 'b' (and 'c' for quadratic),
        'r' (correlation), 'r2' (coefficient of determination).
        """
        n = len(x_data)
        if n != len(y_data) or n < 2:
            return {"error": "Argument ERROR"}

        reg_type = reg_type.lower()
        try:
            if reg_type == "linear":
                return self._linear_regression(x_data, y_data)
            elif reg_type == "quadratic":
                return self._quadratic_regression(x_data, y_data)
            elif reg_type == "logarithmic":
                return self._logarithmic_regression(x_data, y_data)
            elif reg_type == "exponential":
                return self._exponential_regression(x_data, y_data)
            elif reg_type == "power":
                return self._power_regression(x_data, y_data)
            else:
                return {"error": "Argument ERROR"}
        except (ValueError, ZeroDivisionError):
            return {"error": "Math ERROR"}
        except Exception:
            return {"error": "Math ERROR"}

    # ── Private regression helpers ────────────────────────────────────────

    def _linear_regression(self, x: list[float], y: list[float]) -> dict:
        """y = a + bx  (CFX-9850G convention: a=intercept, b=slope)."""
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_x2 = sum(xi ** 2 for xi in x)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_y2 = sum(yi ** 2 for yi in y)

        denom = n * sum_x2 - sum_x ** 2
        if abs(denom) < 1e-15:
            return {"error": "Math ERROR"}

        b = (n * sum_xy - sum_x * sum_y) / denom
        a = (sum_y - b * sum_x) / n

        # Correlation coefficient r
        r_denom = math.sqrt(
            (n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)
        )
        r = (
            (n * sum_xy - sum_x * sum_y) / r_denom
            if abs(r_denom) > 1e-15
            else 0.0
        )

        return {
            "a": _fmt(a),
            "b": _fmt(b),
            "r": _fmt(r),
            "r2": _fmt(r ** 2),
        }

    def _quadratic_regression(self, x: list[float], y: list[float]) -> dict:
        """y = a + bx + cx²  (using numpy polyfit)."""
        import numpy as np

        if len(x) < 3:
            return {"error": "Argument ERROR"}

        coeffs = np.polyfit(x, y, 2)
        c_val = float(coeffs[0])
        b_val = float(coeffs[1])
        a_val = float(coeffs[2])

        # R² via residuals
        y_pred = [a_val + b_val * xi + c_val * xi ** 2 for xi in x]
        ss_res = sum((yi - yp) ** 2 for yi, yp in zip(y, y_pred))
        mean_y = sum(y) / len(y)
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)
        r2 = 1 - ss_res / ss_tot if abs(ss_tot) > 1e-15 else 0.0

        return {
            "a": _fmt(a_val),
            "b": _fmt(b_val),
            "c": _fmt(c_val),
            "r2": _fmt(r2),
        }

    def _logarithmic_regression(self, x: list[float], y: list[float]) -> dict:
        """y = a + b·ln(x)  →  transform x' = ln(x), fit linear."""
        if any(xi <= 0 for xi in x):
            return {"error": "Math ERROR"}
        ln_x = [math.log(xi) for xi in x]
        return self._linear_regression(ln_x, y)

    def _exponential_regression(self, x: list[float], y: list[float]) -> dict:
        """y = a·e^(bx)  →  transform y' = ln(y), fit linear."""
        if any(yi <= 0 for yi in y):
            return {"error": "Math ERROR"}
        ln_y = [math.log(yi) for yi in y]
        res = self._linear_regression(x, ln_y)
        if "error" in res:
            return res
        # Back-transform: intercept becomes e^a
        return {
            "a": _fmt(math.exp(float(res["a"]))),
            "b": res["b"],
            "r": res.get("r", ""),
            "r2": res.get("r2", ""),
        }

    def _power_regression(self, x: list[float], y: list[float]) -> dict:
        """y = a·x^b  →  ln(y) = ln(a) + b·ln(x), fit linear."""
        if any(xi <= 0 for xi in x) or any(yi <= 0 for yi in y):
            return {"error": "Math ERROR"}
        ln_x = [math.log(xi) for xi in x]
        ln_y = [math.log(yi) for yi in y]
        res = self._linear_regression(ln_x, ln_y)
        if "error" in res:
            return res
        return {
            "a": _fmt(math.exp(float(res["a"]))),
            "b": res["b"],
            "r": res.get("r", ""),
            "r2": res.get("r2", ""),
        }
