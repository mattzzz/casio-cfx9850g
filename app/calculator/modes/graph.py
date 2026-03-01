"""GRAPH mode for the Casio CFX-9850G emulator.

Stores up to 3 Y= functions and a view window.
Plotting is done server-side via Matplotlib → inline SVG.
"""

from __future__ import annotations
import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from app.calculator.engine import CalculatorEngine, _make_trig_local, _TRANSFORMATIONS
from sympy.parsing.sympy_parser import parse_expr
import sympy as sp


# ── Default view window (matches CFX-9850G factory defaults) ─────────────────
DEFAULT_WINDOW = {
    "xmin": -6.3, "xmax": 6.3,
    "xscl": 1.0,
    "ymin": -3.1, "ymax": 3.1,
    "yscl": 1.0,
}

# CFX-9850G graph colours (orange / blue / green per zone)
PLOT_COLORS = ["#ff6600", "#0044cc", "#009900"]


class GraphMode:
    def __init__(self, engine: CalculatorEngine):
        self.engine = engine
        self.functions: list[str] = ["", "", ""]   # Y1, Y2, Y3
        self.window: dict = dict(DEFAULT_WINDOW)
        self.trace_on: bool = False

    # ── function store ────────────────────────────────────────────────────────

    def set_function(self, index: int, expr: str) -> None:
        """Set Y<index+1> (0-based). expr is a SymPy-parseable string in X."""
        if 0 <= index < 3:
            self.functions[index] = expr.strip()

    def set_window(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if k in self.window:
                self.window[k] = float(v)

    def reset_window(self) -> None:
        self.window = dict(DEFAULT_WINDOW)

    # ── plotting ──────────────────────────────────────────────────────────────

    def plot(self, width_px: int = 384, height_px: int = 192) -> str:
        """Render all non-empty Y= functions. Returns inline SVG string."""
        w = self.window
        xmin, xmax = w["xmin"], w["xmax"]
        ymin, ymax = w["ymin"], w["ymax"]

        dpi = 96
        fig_w = width_px / dpi
        fig_h = height_px / dpi

        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
        fig.patch.set_facecolor("#a8b84b")
        ax.set_facecolor("#a8b84b")

        # Axes styling to match CFX-9850G LCD look
        ax.spines["left"].set_color("#1c2314")
        ax.spines["bottom"].set_color("#1c2314")
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.tick_params(colors="#1c2314", labelsize=5)
        ax.xaxis.set_major_locator(ticker.MultipleLocator(w["xscl"]))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(w["yscl"]))
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

        # Draw axes through origin
        ax.axhline(0, color="#1c2314", linewidth=0.6, zorder=1)
        ax.axvline(0, color="#1c2314", linewidth=0.6, zorder=1)

        x_vals = np.linspace(xmin, xmax, 500)
        plotted = False

        for i, expr_str in enumerate(self.functions):
            if not expr_str:
                continue
            y_vals = self._eval_function(expr_str, x_vals)
            if y_vals is not None:
                # Mask discontinuities (e.g. tan asymptotes)
                y_masked = np.where(np.abs(y_vals) > 1e6, np.nan, y_vals)
                ax.plot(x_vals, y_masked,
                        color=PLOT_COLORS[i],
                        linewidth=1.2,
                        zorder=2,
                        label=f"Y{i+1}")
                plotted = True

        if not plotted:
            ax.text(0.5, 0.5, "No functions", transform=ax.transAxes,
                    ha="center", va="center", fontsize=6, color="#1c2314")

        plt.tight_layout(pad=0.1)

        buf = io.BytesIO()
        fig.savefig(buf, format="svg", bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        return buf.getvalue().decode("utf-8")

    def _eval_function(self, expr_str: str, x_vals: np.ndarray):
        """Evaluate expr_str over x_vals using SymPy then numpy."""
        local_dict = _make_trig_local(self.engine.angle_mode, self.engine.memory)
        local_dict["X"] = sp.Symbol("X")
        try:
            sym_expr = parse_expr(
                expr_str,
                local_dict=local_dict,
                transformations=_TRANSFORMATIONS,
            )
            f = sp.lambdify(sp.Symbol("X"), sym_expr, modules="numpy")
            result = f(x_vals)
            if np.isscalar(result):
                result = np.full_like(x_vals, float(result))
            return np.array(result, dtype=float)
        except Exception:
            return None

    # ── zoom helpers ──────────────────────────────────────────────────────────

    def zoom_in(self, factor: float = 0.5) -> None:
        w = self.window
        cx = (w["xmin"] + w["xmax"]) / 2
        cy = (w["ymin"] + w["ymax"]) / 2
        rx = (w["xmax"] - w["xmin"]) / 2 * factor
        ry = (w["ymax"] - w["ymin"]) / 2 * factor
        w["xmin"], w["xmax"] = cx - rx, cx + rx
        w["ymin"], w["ymax"] = cy - ry, cy + ry

    def zoom_out(self, factor: float = 2.0) -> None:
        self.zoom_in(factor)

    def zoom_standard(self) -> None:
        self.window.update({"xmin": -10, "xmax": 10,
                            "ymin": -10, "ymax": 10,
                            "xscl": 1, "yscl": 1})

    def zoom_trig(self) -> None:
        """Zoom preset suited for trig functions in DEG mode."""
        self.window.update({"xmin": -360, "xmax": 360,
                            "ymin": -1.6, "ymax": 1.6,
                            "xscl": 90, "yscl": 0.5})
