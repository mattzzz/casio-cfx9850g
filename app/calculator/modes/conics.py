"""CONICS mode for Casio CFX-9850G emulator.

Supports: parabola, circle, ellipse, hyperbola.
Returns inline SVG via Matplotlib (server-side rendering).
"""

from __future__ import annotations

import io

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


class ConicsMode:
    """Plot conic sections and return inline SVG."""

    def plot(self, conic_type: str, params: dict) -> dict:
        """Plot a conic section and return inline SVG.

        conic_type: 'parabola' | 'circle' | 'ellipse' | 'hyperbola'

        params for parabola:  {a, h, k, orientation='vertical'|'horizontal'}
          vertical:   y = a(x-h)² + k
          horizontal: x = a(y-k)² + h

        params for circle:    {h, k, r}
          (x-h)² + (y-k)² = r²

        params for ellipse:   {h, k, a, b}
          (x-h)²/a² + (y-k)²/b² = 1

        params for hyperbola: {h, k, a, b, orientation='horizontal'|'vertical'}
          horizontal: (x-h)²/a² - (y-k)²/b² = 1
          vertical:   (y-k)²/a² - (x-h)²/b² = 1

        Returns: {"svg": "...", "equation": "..."}
        """
        conic_type = conic_type.lower()

        try:
            fig, ax = plt.subplots(figsize=(5, 5))
            ax.set_facecolor("#a8b84b")
            fig.patch.set_facecolor("#a8b84b")
            ax.axhline(0, color="#1c2314", linewidth=0.5)
            ax.axvline(0, color="#1c2314", linewidth=0.5)
            ax.grid(True, color="#1c2314", alpha=0.3, linewidth=0.5)

            if conic_type == "parabola":
                eq_str = self._plot_parabola(ax, params)
            elif conic_type == "circle":
                eq_str = self._plot_circle(ax, params)
            elif conic_type == "ellipse":
                eq_str = self._plot_ellipse(ax, params)
            elif conic_type == "hyperbola":
                eq_str = self._plot_hyperbola(ax, params)
            else:
                plt.close(fig)
                return {"error": "Argument ERROR"}

            ax.set_aspect("equal")
            plt.tight_layout()

            svg_buf = io.StringIO()
            fig.savefig(svg_buf, format="svg")
            plt.close(fig)

            return {"svg": svg_buf.getvalue(), "equation": eq_str}

        except (ValueError, ZeroDivisionError) as exc:
            plt.close("all")
            return {"error": str(exc)}
        except Exception:
            plt.close("all")
            return {"error": "Math ERROR"}

    # ── Private plotters ──────────────────────────────────────────────────

    def _plot_parabola(self, ax, params: dict) -> str:
        a = float(params.get("a", 1))
        h = float(params.get("h", 0))
        k = float(params.get("k", 0))
        orientation = params.get("orientation", "vertical")

        if orientation == "horizontal":
            y = np.linspace(-10, 10, 600)
            x = a * (y - k) ** 2 + h
            ax.plot(x, y, color="#004d1a", linewidth=2)
            margin = max(1.0, (max(x) - min(x)) * 0.1)
            ax.set_xlim(min(x) - margin, max(x) + margin)
            ax.set_ylim(-10, 10)
            k_sign = "-" if k >= 0 else "+"
            k_abs = abs(k)
            h_sign = "+" if h >= 0 else ""
            return f"X={a}(Y{k_sign}{k_abs})\u00b2{h_sign}{h}"
        else:
            x = np.linspace(-10, 10, 600)
            y = a * (x - h) ** 2 + k
            ax.plot(x, y, color="#004d1a", linewidth=2)
            ax.set_xlim(-10, 10)
            margin = max(1.0, (max(y) - min(y)) * 0.1)
            ax.set_ylim(min(y) - margin, max(y) + margin)
            h_sign = "-" if h >= 0 else "+"
            h_abs = abs(h)
            k_sign = "+" if k >= 0 else ""
            return f"Y={a}(X{h_sign}{h_abs})\u00b2{k_sign}{k}"

    def _plot_circle(self, ax, params: dict) -> str:
        h = float(params.get("h", 0))
        k = float(params.get("k", 0))
        r = float(params.get("r", 1))
        if r <= 0:
            raise ValueError("Radius must be positive")
        circle = mpatches.Circle(
            (h, k), r, fill=False, color="#004d1a", linewidth=2
        )
        ax.add_patch(circle)
        ax.set_xlim(h - r - 1, h + r + 1)
        ax.set_ylim(k - r - 1, k + r + 1)
        h_sign = "-" if h >= 0 else "+"
        h_abs = abs(h)
        k_sign = "-" if k >= 0 else "+"
        k_abs = abs(k)
        return f"(X{h_sign}{h_abs})\u00b2+(Y{k_sign}{k_abs})\u00b2={r ** 2}"

    def _plot_ellipse(self, ax, params: dict) -> str:
        h = float(params.get("h", 0))
        k = float(params.get("k", 0))
        a = float(params.get("a", 2))
        b = float(params.get("b", 1))
        if a <= 0 or b <= 0:
            raise ValueError("Semi-axes must be positive")
        ellipse = mpatches.Ellipse(
            (h, k), 2 * a, 2 * b, fill=False, color="#004d1a", linewidth=2
        )
        ax.add_patch(ellipse)
        ax.set_xlim(h - a - 1, h + a + 1)
        ax.set_ylim(k - b - 1, k + b + 1)
        return f"(X-{h})\u00b2/{a ** 2}+(Y-{k})\u00b2/{b ** 2}=1"

    def _plot_hyperbola(self, ax, params: dict) -> str:
        h = float(params.get("h", 0))
        k = float(params.get("k", 0))
        a = float(params.get("a", 1))
        b = float(params.get("b", 1))
        orientation = params.get("orientation", "horizontal")

        if orientation == "horizontal":
            # (x-h)²/a² - (y-k)²/b² = 1
            x_right = np.linspace(h + a, h + 10, 600)
            x_left = np.linspace(h - 10, h - a, 600)
            for x_branch in [x_right, x_left]:
                disc = ((x_branch - h) / a) ** 2 - 1
                disc = np.maximum(disc, 0)
                y_pos = k + b * np.sqrt(disc)
                y_neg = k - b * np.sqrt(disc)
                ax.plot(x_branch, y_pos, color="#004d1a", linewidth=2)
                ax.plot(x_branch, y_neg, color="#004d1a", linewidth=2)
            ax.set_xlim(h - 8, h + 8)
            ax.set_ylim(k - 8, k + 8)
            return f"(X-{h})\u00b2/{a ** 2}-(Y-{k})\u00b2/{b ** 2}=1"
        else:
            # (y-k)²/a² - (x-h)²/b² = 1
            y_top = np.linspace(k + a, k + 10, 600)
            y_bot = np.linspace(k - 10, k - a, 600)
            for y_branch in [y_top, y_bot]:
                disc = ((y_branch - k) / a) ** 2 - 1
                disc = np.maximum(disc, 0)
                x_pos = h + b * np.sqrt(disc)
                x_neg = h - b * np.sqrt(disc)
                ax.plot(x_pos, y_branch, color="#004d1a", linewidth=2)
                ax.plot(x_neg, y_branch, color="#004d1a", linewidth=2)
            ax.set_xlim(h - 8, h + 8)
            ax.set_ylim(k - 8, k + 8)
            return f"(Y-{k})\u00b2/{a ** 2}-(X-{h})\u00b2/{b ** 2}=1"
