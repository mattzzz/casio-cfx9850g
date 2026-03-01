"""COMP mode state machine for the Casio CFX-9850G emulator.

Maintains the input buffer, SHIFT/ALPHA states, and evaluates on EXE.
Communicates via a dict-based display state.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from app.calculator.engine import CalculatorEngine


@dataclass
class CompState:
    expression: str = ""
    result: str = ""
    error: str = ""
    mode: str = "COMP"
    angle: str = "DEG"
    shift: bool = False
    alpha: bool = False
    insert_mode: bool = True   # always insert for now

    def to_dict(self) -> dict:
        return {
            "type": "display",
            "expression": self.expression,
            "result": self.result,
            "error": self.error,
            "mode": self.mode,
            "angle": self.angle,
            "shift": self.shift,
            "alpha": self.alpha,
        }


# Map key names → text to append to expression buffer
_KEY_INSERT: dict[str, str] = {
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    "DOT": ".", "EXP": "E",
    "PLUS": "+", "MINUS": "-", "MUL": "*", "DIV": "/",
    "LPAREN": "(", "RPAREN": ")",
    "COMMA": ",",
    "SIN": "sin(", "COS": "cos(", "TAN": "tan(",
    "LOG": "log(", "LN": "ln(",
    "SQRT": "sqrt(", "SQR": "**2",
    "POW": "**", "INV": "**(-1)",
    "PI": "pi", "E_CONST": "e",
    "ANS": "Ans",
    # Negative sign (unary minus on number pad)
    "NEG": "(-",
}

# SHIFT modifier → different key action
_KEY_INSERT_SHIFT: dict[str, str] = {
    "SIN": "asin(", "COS": "acos(", "TAN": "atan(",
    "LOG": "10**(", "LN": "e**(",
    "SQRT": "**3",        # cube — approximation
    "SQR": "sqrt(",       # √ on SHIFT+x²
}

# ALPHA modifier → variable letter (matches rlbl labels on the HTML keyboard)
# Row: X,θ,T  log  ln  sin  cos  tan
# Row: ab/c   F→D  (    )    ,    →
# Row: 7  8  9 | 4  5  6 | ×  ÷ | 1  2  3 | +  -  | 0
_ALPHA_KEYS: dict[str, str] = {
    "XTHETA": "A",
    "LOG":    "B",
    "LN":     "C",
    "SIN":    "D",
    "COS":    "E",
    "TAN":    "F",
    "FRAC":   "G",   # ab/c key
    "FD":     "H",   # F→D key
    "LPAREN": "I",
    "RPAREN": "J",
    "COMMA":  "K",
    "ARROW":  "L",
    "7": "M", "8": "N", "9": "O",
    "4": "P", "5": "Q", "6": "R",
    "MUL":    "S",   # ×
    "DIV":    "T",   # ÷
    "1": "U", "2": "V", "3": "W",
    "PLUS":   "X",
    "MINUS":  "Y",
    "0": "Z",
    # Special ALPHA combinations (non-letter)
    "EXP":    "pi",  # ALPHA + EXP = π constant
    "NEG":    "Ans", # ALPHA + (-) = Ans
}


class CompMode:
    def __init__(self, engine: CalculatorEngine):
        self.engine = engine
        self.state = CompState()
        # Replay buffer: stores last 7 successfully-executed expressions
        self._replay: list[str] = []
        # -1 = not browsing; 0 = most recent; 1 = second-most-recent; etc.
        self._replay_idx: int = -1
        self._saved_expr: str = ""  # expression saved before entering replay mode
        # After a successful EXE, the next insert key starts a fresh expression
        # (matches real CFX-9850G behaviour — EXE result is shown, then cleared)
        self._after_result: bool = False

    # ── public entry point ────────────────────────────────────────────────

    def handle_key(self, key: str) -> dict:
        """Process one key press. Returns the new display state dict."""
        s = self.state
        k = key.upper()

        # ── replay buffer navigation ──────────────────────────────────────
        if k == "UP":
            if self._replay:
                if self._replay_idx == -1:
                    # Enter replay mode — save current expression
                    self._saved_expr = s.expression
                    self._replay_idx = 0
                elif self._replay_idx < len(self._replay) - 1:
                    self._replay_idx += 1
                # Show entry at current index (0 = most recent = last in list)
                s.expression = self._replay[-(self._replay_idx + 1)]
                s.result = ""
                s.error = ""
            return s.to_dict()

        if k == "DOWN":
            if self._replay_idx >= 0:
                self._replay_idx -= 1
                if self._replay_idx == -1:
                    # Restore expression that was typed before replay
                    s.expression = self._saved_expr
                else:
                    s.expression = self._replay[-(self._replay_idx + 1)]
                s.result = ""
                s.error = ""
            return s.to_dict()

        # Any non-navigation key exits replay mode without restoring
        self._replay_idx = -1

        # ── modifier keys ─────────────────────────────────────────────────
        if k == "SHIFT":
            s.shift = not s.shift
            s.alpha = False
            return s.to_dict()

        if k == "ALPHA":
            s.alpha = not s.alpha
            s.shift = False
            return s.to_dict()

        # ── system keys ───────────────────────────────────────────────────
        if k == "AC":
            s.expression = ""
            s.result = ""
            s.error = ""
            s.shift = False
            s.alpha = False
            self._after_result = False
            return s.to_dict()

        if k == "DEL":
            if s.expression:
                s.expression = s.expression[:-1]
            s.shift = False
            s.alpha = False
            self._after_result = False
            return s.to_dict()

        if k == "EXE":
            self._execute()
            s.shift = False
            s.alpha = False
            return s.to_dict()

        # ── angle mode (SHIFT+7 = DRG on real calc; simpler here) ─────────
        if k == "DEG":
            self.engine.set_angle_mode("DEG")
            s.angle = "DEG"
            s.shift = False
            return s.to_dict()
        if k == "RAD":
            self.engine.set_angle_mode("RAD")
            s.angle = "RAD"
            s.shift = False
            return s.to_dict()
        if k == "GRD":
            self.engine.set_angle_mode("GRD")
            s.angle = "GRD"
            s.shift = False
            return s.to_dict()

        # ── STO: store Ans into variable (SHIFT + RCL) ────────────────────
        if k == "STO" and s.alpha:
            # Next key will be the variable — handled client-side by sending
            # a STORE:<var> key
            s.alpha = False
            return s.to_dict()

        if k.startswith("STORE:"):
            var = k[6:].upper()
            if var in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                ans_val = str(self.engine.memory.get_ans())
                self.engine.store_variable(var, ans_val)
            s.shift = False
            s.alpha = False
            return s.to_dict()

        # ── ALPHA: insert variable letter ─────────────────────────────────
        if s.alpha:
            letter = _ALPHA_KEYS.get(k)
            if letter:
                if self._after_result:
                    s.expression = ""
                    self._after_result = False
                s.expression += letter
            s.alpha = False
            return s.to_dict()

        # ── SHIFT: alternate key function ─────────────────────────────────
        if s.shift:
            text = _KEY_INSERT_SHIFT.get(k) or _KEY_INSERT.get(k)
            if text:
                if self._after_result:
                    s.expression = ""
                    self._after_result = False
                s.expression += text
            s.shift = False
            return s.to_dict()

        # ── normal key insert ─────────────────────────────────────────────
        text = _KEY_INSERT.get(k)
        if text:
            # After EXE showed a result, the next insert key starts fresh
            if self._after_result:
                s.expression = ""
                self._after_result = False
            s.expression += text
        return s.to_dict()

    # ── private ───────────────────────────────────────────────────────────

    def _execute(self):
        s = self.state
        if not s.expression.strip():
            return
        # Exit replay mode when executing
        self._replay_idx = -1
        result = self.engine.evaluate(s.expression)
        if "ERROR" in result:
            s.error = result
            s.result = ""
        else:
            s.result = result
            s.error = ""
            # Push successfully-executed expression to replay buffer (max 7)
            expr = s.expression
            if expr and (not self._replay or self._replay[-1] != expr):
                self._replay.append(expr)
                if len(self._replay) > 7:
                    self._replay.pop(0)
            # Next insert key will start a new expression (real CFX-9850G behaviour)
            self._after_result = True
