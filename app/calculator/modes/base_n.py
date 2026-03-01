"""BASE-N mode for Casio CFX-9850G emulator.

Conversions between DEC / HEX / BIN / OCT.
Bitwise operations: AND, OR, XOR, NOT, shift left/right.

The CFX-9850G BASE-N mode uses 32-bit signed integers (two's complement).
"""

from __future__ import annotations

_MAX_INT = 2 ** 31 - 1   # +2 147 483 647
_MIN_INT = -(2 ** 31)    # -2 147 483 648
_MASK32 = 0xFFFF_FFFF


def _to_signed32(n: int) -> int:
    """Convert any integer to 32-bit signed value (two's complement)."""
    n = n & _MASK32
    if n >= 2 ** 31:
        n -= 2 ** 32
    return n


def _parse(value: str, base: str) -> int:
    """Parse value string in the given base; return signed 32-bit int."""
    bases = {"DEC": 10, "HEX": 16, "BIN": 2, "OCT": 8}
    if base not in bases:
        raise ValueError(f"Unknown base: {base}")
    raw = int(value.strip(), bases[base])
    return _to_signed32(raw)


def _format_base(n: int, base: str) -> str:
    """Format a (possibly negative) 32-bit integer in the given base."""
    if base == "DEC":
        return str(n)
    # For non-decimal: use unsigned 32-bit representation
    unsigned = n & _MASK32
    if base == "HEX":
        return hex(unsigned)[2:].upper()
    elif base == "BIN":
        return bin(unsigned)[2:]
    elif base == "OCT":
        return oct(unsigned)[2:]
    raise ValueError(f"Unknown base: {base}")


class BaseNMode:
    """Casio CFX-9850G BASE-N mode."""

    # ── Conversion ────────────────────────────────────────────────────────

    def convert(self, value: str, from_base: str, to_base: str) -> dict:
        """Convert value (string) from from_base to to_base.

        Bases: 'DEC', 'HEX', 'BIN', 'OCT'
        Returns: {"result": "...", "base": to_base}
        """
        from_base = from_base.upper()
        to_base = to_base.upper()
        try:
            n = _parse(value, from_base)
            result = _format_base(n, to_base)
            return {"result": result, "base": to_base}
        except (ValueError, KeyError):
            return {"error": "Syntax ERROR"}

    def to_dec(self, value: str, from_base: str) -> dict:
        """Convert from any base to DEC."""
        return self.convert(value, from_base, "DEC")

    def from_dec(self, value: int, to_base: str) -> dict:
        """Convert a decimal integer to the given base."""
        to_base = to_base.upper()
        try:
            n = _to_signed32(int(value))
            result = _format_base(n, to_base)
            return {"result": result, "base": to_base}
        except (ValueError, KeyError):
            return {"error": "Argument ERROR"}

    # ── Bitwise operations ────────────────────────────────────────────────

    def bitwise_and(self, a: int, b: int) -> dict:
        result = _to_signed32(int(a) & int(b))
        return {"result": str(result)}

    def bitwise_or(self, a: int, b: int) -> dict:
        result = _to_signed32(int(a) | int(b))
        return {"result": str(result)}

    def bitwise_xor(self, a: int, b: int) -> dict:
        result = _to_signed32(int(a) ^ int(b))
        return {"result": str(result)}

    def bitwise_not(self, a: int) -> dict:
        """Bitwise NOT (32-bit complement, signed result)."""
        result = _to_signed32(~int(a) & _MASK32)
        return {"result": str(result)}

    def shift_left(self, a: int, bits: int) -> dict:
        """Logical shift left; result clamped to 32-bit signed."""
        result = _to_signed32((int(a) << int(bits)) & _MASK32)
        return {"result": str(result)}

    def shift_right(self, a: int, bits: int) -> dict:
        """Arithmetic right shift (sign-extending)."""
        result = int(a) >> int(bits)
        return {"result": str(result)}
