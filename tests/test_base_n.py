"""BASE-N mode tests.

Tests BaseNMode directly and via the REST API.
"""

import pytest
from app.calculator.modes.base_n import BaseNMode


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def bn():
    return BaseNMode()


# ── Conversion: DEC → other bases ─────────────────────────────────────────────

class TestFromDec:
    def test_dec_to_hex_zero(self, bn):
        assert bn.from_dec(0, "HEX")["result"] == "0"

    def test_dec_to_hex_255(self, bn):
        assert bn.from_dec(255, "HEX")["result"] == "FF"

    def test_dec_to_hex_256(self, bn):
        assert bn.from_dec(256, "HEX")["result"] == "100"

    def test_dec_to_bin_1(self, bn):
        assert bn.from_dec(1, "BIN")["result"] == "1"

    def test_dec_to_bin_8(self, bn):
        assert bn.from_dec(8, "BIN")["result"] == "1000"

    def test_dec_to_bin_255(self, bn):
        assert bn.from_dec(255, "BIN")["result"] == "11111111"

    def test_dec_to_oct_8(self, bn):
        assert bn.from_dec(8, "OCT")["result"] == "10"

    def test_dec_to_oct_64(self, bn):
        assert bn.from_dec(64, "OCT")["result"] == "100"


# ── Conversion: other bases → DEC ─────────────────────────────────────────────

class TestToDec:
    def test_hex_to_dec_ff(self, bn):
        assert bn.to_dec("FF", "HEX")["result"] == "255"

    def test_hex_to_dec_100(self, bn):
        assert bn.to_dec("100", "HEX")["result"] == "256"

    def test_bin_to_dec_1000(self, bn):
        assert bn.to_dec("1000", "BIN")["result"] == "8"

    def test_oct_to_dec_17(self, bn):
        assert bn.to_dec("17", "OCT")["result"] == "15"

    def test_oct_to_dec_10(self, bn):
        assert bn.to_dec("10", "OCT")["result"] == "8"


# ── Generic convert ───────────────────────────────────────────────────────────

class TestConvert:
    def test_hex_to_bin(self, bn):
        r = bn.convert("F", "HEX", "BIN")
        assert r["result"] == "1111"

    def test_bin_to_hex(self, bn):
        r = bn.convert("11111111", "BIN", "HEX")
        assert r["result"] == "FF"

    def test_oct_to_hex(self, bn):
        r = bn.convert("377", "OCT", "HEX")
        assert r["result"] == "FF"

    def test_dec_to_dec(self, bn):
        r = bn.convert("42", "DEC", "DEC")
        assert r["result"] == "42"

    def test_invalid_hex_digit(self, bn):
        r = bn.convert("GG", "HEX", "DEC")
        assert "error" in r

    def test_invalid_bin_digit(self, bn):
        r = bn.convert("2", "BIN", "DEC")
        assert "error" in r

    def test_unknown_base(self, bn):
        r = bn.convert("10", "BASE5", "DEC")
        assert "error" in r


# ── Negative numbers (32-bit signed two's complement) ─────────────────────────

class TestNegativeNumbers:
    def test_negative_dec_to_hex(self, bn):
        # -1 in 32-bit two's complement = FFFFFFFF
        r = bn.from_dec(-1, "HEX")
        assert r["result"] == "FFFFFFFF"

    def test_negative_dec_to_bin(self, bn):
        r = bn.from_dec(-1, "BIN")
        assert r["result"] == "11111111111111111111111111111111"

    def test_min_int_stays_signed(self, bn):
        # -2147483648 should come back as -2147483648 in DEC
        r = bn.from_dec(-2147483648, "DEC")
        assert r["result"] == "-2147483648"


# ── Bitwise AND ───────────────────────────────────────────────────────────────

class TestBitwiseAnd:
    def test_and_basic(self, bn):
        assert bn.bitwise_and(12, 10)["result"] == "8"  # 1100 & 1010 = 1000

    def test_and_zero(self, bn):
        assert bn.bitwise_and(255, 0)["result"] == "0"

    def test_and_self(self, bn):
        assert bn.bitwise_and(42, 42)["result"] == "42"

    def test_and_all_ones(self, bn):
        assert bn.bitwise_and(255, 255)["result"] == "255"


# ── Bitwise OR ────────────────────────────────────────────────────────────────

class TestBitwiseOr:
    def test_or_basic(self, bn):
        assert bn.bitwise_or(12, 10)["result"] == "14"  # 1100 | 1010 = 1110

    def test_or_zero(self, bn):
        assert bn.bitwise_or(42, 0)["result"] == "42"

    def test_or_self(self, bn):
        assert bn.bitwise_or(7, 7)["result"] == "7"


# ── Bitwise XOR ───────────────────────────────────────────────────────────────

class TestBitwiseXor:
    def test_xor_basic(self, bn):
        assert bn.bitwise_xor(12, 10)["result"] == "6"  # 1100 ^ 1010 = 0110

    def test_xor_self(self, bn):
        assert bn.bitwise_xor(42, 42)["result"] == "0"

    def test_xor_zero(self, bn):
        assert bn.bitwise_xor(99, 0)["result"] == "99"


# ── Bitwise NOT ───────────────────────────────────────────────────────────────

class TestBitwiseNot:
    def test_not_zero(self, bn):
        # ~0 in 32-bit signed = -1
        assert bn.bitwise_not(0)["result"] == "-1"

    def test_not_minus_one(self, bn):
        # ~(-1) = 0
        assert bn.bitwise_not(-1)["result"] == "0"

    def test_not_1(self, bn):
        # ~1 = -2  (32-bit signed)
        assert bn.bitwise_not(1)["result"] == "-2"


# ── Shift operations ──────────────────────────────────────────────────────────

class TestShift:
    def test_shl_1(self, bn):
        assert bn.shift_left(1, 1)["result"] == "2"

    def test_shl_8_by_4(self, bn):
        assert bn.shift_left(1, 4)["result"] == "16"

    def test_shr_8(self, bn):
        assert bn.shift_right(8, 1)["result"] == "4"

    def test_shr_negative(self, bn):
        # Arithmetic right shift of -8 by 1 = -4
        assert bn.shift_right(-8, 1)["result"] == "-4"

    def test_shl_then_shr(self, bn):
        r1 = bn.shift_left(3, 2)   # 12
        r2 = bn.shift_right(int(r1["result"]), 2)  # 3
        assert r2["result"] == "3"


# ── API endpoint tests ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_basen_convert_hex_to_dec(client):
    resp = await client.post(
        "/api/basen/convert",
        json={"value": "FF", "from_base": "HEX", "to_base": "DEC"},
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "255"


@pytest.mark.anyio
async def test_api_basen_convert_dec_to_bin(client):
    resp = await client.post(
        "/api/basen/convert",
        json={"value": "10", "from_base": "DEC", "to_base": "BIN"},
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "1010"


@pytest.mark.anyio
async def test_api_basen_bitwise_and(client):
    resp = await client.post(
        "/api/basen/bitwise",
        json={"op": "and", "a": 12, "b": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "8"


@pytest.mark.anyio
async def test_api_basen_bitwise_or(client):
    resp = await client.post(
        "/api/basen/bitwise",
        json={"op": "or", "a": 12, "b": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "14"


@pytest.mark.anyio
async def test_api_basen_bitwise_xor(client):
    resp = await client.post(
        "/api/basen/bitwise",
        json={"op": "xor", "a": 12, "b": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "6"


@pytest.mark.anyio
async def test_api_basen_bitwise_not(client):
    resp = await client.post(
        "/api/basen/bitwise",
        json={"op": "not", "a": 0},
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "-1"


@pytest.mark.anyio
async def test_api_basen_shift_left(client):
    resp = await client.post(
        "/api/basen/bitwise",
        json={"op": "shl", "a": 1, "bits": 4},
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == "16"


@pytest.mark.anyio
async def test_api_basen_invalid_op(client):
    resp = await client.post(
        "/api/basen/bitwise",
        json={"op": "nand", "a": 1, "b": 1},
    )
    assert resp.status_code == 200
    assert "error" in resp.json()
