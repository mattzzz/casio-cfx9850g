"""MAT mode tests.

Tests MatrixMode directly and via the REST API endpoint.
"""

import pytest
from app.calculator.modes.matrix import MatrixMode


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mm():
    return MatrixMode()


def approx(a, b, rel=1e-5):
    assert abs(float(a) - float(b)) <= rel * max(abs(float(b)), 1e-10), \
        f"{a} ≉ {b}"


# ── Define ────────────────────────────────────────────────────────────────────

class TestDefine:
    def test_define_2x2(self, mm):
        r = mm.define("A", [[1, 2], [3, 4]])
        assert r["rows"] == 2
        assert r["cols"] == 2

    def test_define_3x3(self, mm):
        r = mm.define("B", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        assert r["rows"] == 3

    def test_define_invalid_name(self, mm):
        r = mm.define("Z", [[1, 2]])
        assert "error" in r

    def test_define_empty_returns_error(self, mm):
        r = mm.define("A", [])
        assert "error" in r

    def test_define_jagged_returns_error(self, mm):
        r = mm.define("A", [[1, 2], [3]])
        assert "error" in r

    def test_get_element(self, mm):
        mm.define("A", [[5, 6], [7, 8]])
        r = mm.get_element("A", 1, 1)
        assert r["value"] == "5"

    def test_get_element_1_based(self, mm):
        mm.define("A", [[10, 20], [30, 40]])
        r = mm.get_element("A", 2, 1)
        assert r["value"] == "30"

    def test_get_element_out_of_bounds(self, mm):
        mm.define("A", [[1, 2], [3, 4]])
        r = mm.get_element("A", 3, 1)
        assert "error" in r

    def test_undefined_matrix(self, mm):
        r = mm.get_element("C", 1, 1)
        assert "error" in r


# ── Arithmetic ────────────────────────────────────────────────────────────────

class TestAdd:
    def test_add_2x2(self, mm):
        mm.define("A", [[1, 2], [3, 4]])
        mm.define("B", [[5, 6], [7, 8]])
        r = mm.add("A", "B")
        assert r["matrix"] == [["6", "8"], ["10", "12"]]

    def test_add_dimension_mismatch(self, mm):
        mm.define("A", [[1, 2], [3, 4]])
        mm.define("B", [[1, 2, 3]])
        r = mm.add("A", "B")
        assert "error" in r

    def test_add_undefined(self, mm):
        mm.define("A", [[1]])
        r = mm.add("A", "F")
        assert "error" in r


class TestSubtract:
    def test_sub_2x2(self, mm):
        mm.define("A", [[5, 6], [7, 8]])
        mm.define("B", [[1, 2], [3, 4]])
        r = mm.subtract("A", "B")
        assert r["matrix"] == [["4", "4"], ["4", "4"]]


class TestMultiply:
    def test_mul_identity(self, mm):
        mm.define("A", [[1, 2], [3, 4]])
        mm.define("B", [[1, 0], [0, 1]])
        r = mm.multiply("A", "B")
        assert r["matrix"] == [["1", "2"], ["3", "4"]]

    def test_mul_2x2(self, mm):
        mm.define("A", [[1, 2], [3, 4]])
        mm.define("B", [[5, 6], [7, 8]])
        r = mm.multiply("A", "B")
        # [1*5+2*7, 1*6+2*8] = [19, 22]
        # [3*5+4*7, 3*6+4*8] = [43, 50]
        assert r["matrix"] == [["19", "22"], ["43", "50"]]

    def test_mul_dimension_mismatch(self, mm):
        mm.define("A", [[1, 2], [3, 4]])
        mm.define("B", [[1, 2, 3]])
        r = mm.multiply("A", "B")
        assert "error" in r

    def test_mul_non_square(self, mm):
        # 2×3 × 3×2
        mm.define("A", [[1, 2, 3], [4, 5, 6]])
        mm.define("B", [[7, 8], [9, 10], [11, 12]])
        r = mm.multiply("A", "B")
        assert "error" not in r
        assert len(r["matrix"]) == 2
        assert len(r["matrix"][0]) == 2


class TestScalarMultiply:
    def test_scalar_mul(self, mm):
        mm.define("A", [[1, 2], [3, 4]])
        r = mm.scalar_multiply(3, "A")
        assert r["matrix"] == [["3", "6"], ["9", "12"]]

    def test_scalar_zero(self, mm):
        mm.define("A", [[5, 6], [7, 8]])
        r = mm.scalar_multiply(0, "A")
        assert r["matrix"] == [["0", "0"], ["0", "0"]]


class TestTranspose:
    def test_transpose_2x2(self, mm):
        mm.define("A", [[1, 2], [3, 4]])
        r = mm.transpose("A")
        assert r["matrix"] == [["1", "3"], ["2", "4"]]

    def test_transpose_non_square(self, mm):
        mm.define("A", [[1, 2, 3], [4, 5, 6]])
        r = mm.transpose("A")
        assert len(r["matrix"]) == 3
        assert len(r["matrix"][0]) == 2


# ── Determinant ───────────────────────────────────────────────────────────────

class TestDeterminant:
    def test_det_2x2(self, mm):
        mm.define("A", [[1, 2], [3, 4]])
        r = mm.determinant("A")
        approx(r["result"], -2)

    def test_det_identity_3x3(self, mm):
        mm.define("A", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        r = mm.determinant("A")
        approx(r["result"], 1)

    def test_det_singular(self, mm):
        mm.define("A", [[1, 2], [2, 4]])   # rows are dependent
        r = mm.determinant("A")
        approx(r["result"], 0)

    def test_det_non_square(self, mm):
        mm.define("A", [[1, 2, 3], [4, 5, 6]])
        r = mm.determinant("A")
        assert "error" in r


# ── Inverse ───────────────────────────────────────────────────────────────────

class TestInverse:
    def test_inv_2x2(self, mm):
        mm.define("A", [[4, 7], [2, 6]])
        r = mm.inverse("A")
        assert "error" not in r
        # A^-1 of [[4,7],[2,6]] = [[0.6,-0.7],[-0.2,0.4]]
        approx(r["matrix"][0][0], 0.6)
        approx(r["matrix"][0][1], -0.7)

    def test_inv_singular(self, mm):
        mm.define("A", [[1, 2], [2, 4]])
        r = mm.inverse("A")
        assert "error" in r

    def test_inv_identity(self, mm):
        mm.define("A", [[1, 0], [0, 1]])
        r = mm.inverse("A")
        assert r["matrix"] == [["1", "0"], ["0", "1"]]


# ── RREF ──────────────────────────────────────────────────────────────────────

class TestRREF:
    def test_rref_identity(self, mm):
        mm.define("A", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        r = mm.rref("A")
        assert "error" not in r
        assert r["matrix"] == [["1", "0", "0"],
                                ["0", "1", "0"],
                                ["0", "0", "1"]]

    def test_rref_basic(self, mm):
        # [[2, 4], [1, 2]] → [[1, 2], [0, 0]]
        mm.define("A", [[2, 4], [1, 2]])
        r = mm.rref("A")
        assert "error" not in r
        approx(r["matrix"][0][0], 1)
        approx(r["matrix"][0][1], 2)

    def test_rref_augmented(self, mm):
        # System: x + y = 3, 2x - y = 0 → augmented [[1,1,3],[2,-1,0]]
        mm.define("A", [[1, 1, 3], [2, -1, 0]])
        r = mm.rref("A")
        assert "error" not in r


# ── API endpoint tests ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_matrix_calculate_det(client):
    resp = await client.post(
        "/api/matrix/calculate",
        json={
            "op": "det",
            "a": "A",
            "matrices": {"A": [[1, 2], [3, 4]]},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data
    approx(data["result"], -2)


@pytest.mark.anyio
async def test_api_matrix_calculate_add(client):
    resp = await client.post(
        "/api/matrix/calculate",
        json={
            "op": "add",
            "a": "A",
            "b": "B",
            "matrices": {
                "A": [[1, 0], [0, 1]],
                "B": [[1, 0], [0, 1]],
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matrix"] == [["2", "0"], ["0", "2"]]


@pytest.mark.anyio
async def test_api_matrix_calculate_inv(client):
    resp = await client.post(
        "/api/matrix/calculate",
        json={
            "op": "inv",
            "a": "A",
            "matrices": {"A": [[2, 0], [0, 2]]},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    approx(data["matrix"][0][0], 0.5)
