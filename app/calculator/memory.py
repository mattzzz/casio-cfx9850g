"""Variable and memory store for the Casio CFX-9850G emulator.

Variables: A–Z (26 letters) + Ans
Matrices: A–F (Phase 4)
"""

import sympy as sp


class MemoryStore:
    def __init__(self):
        # A–Z variables, initialised to 0
        self._vars: dict[str, sp.Basic] = {
            letter: sp.Integer(0) for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        }
        self._vars["Ans"] = sp.Integer(0)

    def get(self, name: str) -> sp.Basic:
        return self._vars.get(name, sp.Integer(0))

    def set(self, name: str, value: sp.Basic) -> None:
        self._vars[name] = value

    def set_ans(self, value: sp.Basic) -> None:
        self._vars["Ans"] = value

    def get_ans(self) -> sp.Basic:
        return self._vars["Ans"]

    def as_sympy_dict(self) -> dict[str, sp.Basic]:
        """Return a copy suitable for use as parse_expr local_dict."""
        return dict(self._vars)

    def clear_all(self) -> None:
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            self._vars[letter] = sp.Integer(0)
        self._vars["Ans"] = sp.Integer(0)
