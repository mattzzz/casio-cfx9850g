"""EQUA mode tests.

Tests EquationMode directly and via the REST API.
"""

import pytest
from app.calculator.modes.equation import EquationMode


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def em():
    return EquationMode()


def approx_val(a, b, rel=1e-5):
    assert abs(float(a) - float(b)) <= rel * max(abs(float(b)), 1e-10), \
        f"{a} ≉ {b}"


# ── Polynomial solver ─────────────────────────────────────────────────────────

class TestPolynomial:
    # Degree 2: x² - 5x + 6 = 0  →  roots 2, 3
    def test_quadratic_integer_roots(self, em):
        r = em.polynomial([1, -5, 6])
        assert "error" not in r
        assert r["degree"] == 2
        roots = sorted([float(x) for x in r["roots"]])
        approx_val(roots[0], 2)
        approx_val(roots[1], 3)

    # x² + 1 = 0  →  ±i  (complex roots)
    def test_quadratic_complex_roots(self, em):
        r = em.polynomial([1, 0, 1])
        assert "error" not in r
        assert r["degree"] == 2
        assert len(r["roots"]) == 2
        # Both roots should contain 'i'
        assert all("i" in root for root in r["roots"])

    # x² - 4 = 0  →  ±2
    def test_quadratic_symmetric(self, em):
        r = em.polynomial([1, 0, -4])
        roots = sorted([float(x) for x in r["roots"]])
        approx_val(roots[0], -2)
        approx_val(roots[1], 2)

    # x² + 2x + 1 = 0  →  double root at -1
    def test_quadratic_double_root(self, em):
        r = em.polynomial([1, 2, 1])
        assert "error" not in r
        roots = [float(x) for x in r["roots"]]
        for root in roots:
            approx_val(root, -1)

    # Degree 3: x³ - 6x² + 11x - 6 = 0  →  roots 1, 2, 3
    def test_cubic_three_real_roots(self, em):
        r = em.polynomial([1, -6, 11, -6])
        assert "error" not in r
        assert r["degree"] == 3
        roots = sorted([float(x) for x in r["roots"]])
        approx_val(roots[0], 1)
        approx_val(roots[1], 2)
        approx_val(roots[2], 3)

    # Degree 4
    def test_degree_4(self, em):
        # x⁴ - 1 = 0 → roots ±1, ±i
        r = em.polynomial([1, 0, 0, 0, -1])
        assert "error" not in r
        assert r["degree"] == 4
        assert len(r["roots"]) == 4

    # Degree 5
    def test_degree_5(self, em):
        r = em.polynomial([1, 0, 0, 0, 0, -1])
        assert "error" not in r
        assert r["degree"] == 5

    # Degree 6
    def test_degree_6(self, em):
        r = em.polynomial([1, 0, 0, 0, 0, 0, -1])
        assert "error" not in r
        assert r["degree"] == 6

    # Degree 1 → error (not supported)
    def test_degree_1_error(self, em):
        r = em.polynomial([1, -3])
        assert "error" in r

    # Leading zero → error
    def test_leading_zero_error(self, em):
        r = em.polynomial([0, 1, -3])
        assert "error" in r

    # Degree 7 → error
    def test_degree_7_error(self, em):
        r = em.polynomial([1, 0, 0, 0, 0, 0, 0, -1])
        assert "error" in r


# ── Simultaneous equations ────────────────────────────────────────────────────

class TestSimultaneous:
    # 2×2: x + y = 5, 2x - y = 1  →  x=2, y=3
    def test_2x2_basic(self, em):
        r = em.simultaneous([[1, 1], [2, -1]], [5, 1])
        assert "error" not in r
        sol = r["solution"]
        approx_val(sol[0], 2)
        approx_val(sol[1], 3)

    # 3×3 identity
    def test_3x3_identity(self, em):
        r = em.simultaneous(
            [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            [7, 8, 9],
        )
        assert "error" not in r
        sol = r["solution"]
        approx_val(sol[0], 7)
        approx_val(sol[1], 8)
        approx_val(sol[2], 9)

    # Singular → error
    def test_singular_no_solution(self, em):
        # x + y = 1, 2x + 2y = 5  → inconsistent
        r = em.simultaneous([[1, 1], [2, 2]], [1, 5])
        assert "error" in r

    # Dependent (infinite solutions)
    def test_infinite_solutions(self, em):
        r = em.simultaneous([[1, 1], [2, 2]], [3, 6])
        assert "error" in r
        assert "Infinite" in r["error"] or "error" in r

    # Dimension mismatch
    def test_matrix_too_small(self, em):
        r = em.simultaneous([[1]], [5])
        assert "error" in r

    # 4×4 system
    def test_4x4(self, em):
        # Diagonal system: 2x=4, 3y=9, 4z=8, 5w=15
        r = em.simultaneous(
            [[2, 0, 0, 0], [0, 3, 0, 0], [0, 0, 4, 0], [0, 0, 0, 5]],
            [4, 9, 8, 15],
        )
        assert "error" not in r
        sol = r["solution"]
        approx_val(sol[0], 2)
        approx_val(sol[1], 3)
        approx_val(sol[2], 2)
        approx_val(sol[3], 3)

    # Wrong constant count
    def test_mismatched_constants(self, em):
        r = em.simultaneous([[1, 1], [2, 3]], [5])
        assert "error" in r


# ── API endpoint tests ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_equa_polynomial(client):
    resp = await client.post(
        "/api/equa/polynomial", json={"coefficients": [1, -5, 6]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["degree"] == 2
    roots = sorted([float(x) for x in data["roots"]])
    approx_val(roots[0], 2)
    approx_val(roots[1], 3)


@pytest.mark.anyio
async def test_api_equa_simultaneous(client):
    resp = await client.post(
        "/api/equa/simultaneous",
        json={"matrix": [[1, 1], [2, -1]], "constants": [5, 1]},
    )
    assert resp.status_code == 200
    data = resp.json()
    sol = data["solution"]
    approx_val(sol[0], 2)
    approx_val(sol[1], 3)
