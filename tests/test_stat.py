"""STAT mode tests.

Tests StatMode directly and via the REST API endpoints.
"""

import pytest
from app.calculator.modes.stat import StatMode


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sm():
    return StatMode()


# ── Helper ────────────────────────────────────────────────────────────────────

def approx(a, b, rel=1e-5):
    assert abs(float(a) - float(b)) <= rel * max(abs(float(b)), 1e-10), \
        f"{a} ≉ {b}"


# ── 1-variable statistics ─────────────────────────────────────────────────────

class TestOneVar:
    def test_count(self, sm):
        r = sm.one_var([1, 2, 3, 4, 5])
        assert r["n"] == 5

    def test_mean(self, sm):
        r = sm.one_var([2, 4, 6])
        approx(r["mean_x"], 4)

    def test_sum_x(self, sm):
        r = sm.one_var([1, 2, 3])
        assert r["sum_x"] == "6"

    def test_sum_x2(self, sm):
        r = sm.one_var([1, 2, 3])
        assert r["sum_x2"] == "14"

    def test_sigma_x_population(self, sm):
        # σ of [2, 4, 4, 4, 5, 5, 7, 9] = 2
        r = sm.one_var([2, 4, 4, 4, 5, 5, 7, 9])
        approx(r["sigma_x"], 2.0)

    def test_s_x_sample(self, sm):
        # S of [2, 4, 4, 4, 5, 5, 7, 9] = sqrt(32/7) ≈ 2.138
        r = sm.one_var([2, 4, 4, 4, 5, 5, 7, 9])
        import math
        approx(r["s_x"], math.sqrt(sum((x - 5.0) ** 2 for x in [2,4,4,4,5,5,7,9]) / 7))

    def test_min_max(self, sm):
        r = sm.one_var([7, 3, 9, 1, 5])
        assert r["min_x"] == "1"
        assert r["max_x"] == "9"

    def test_median_odd(self, sm):
        r = sm.one_var([3, 1, 4, 1, 5])
        approx(r["median"], 3.0)

    def test_median_even(self, sm):
        r = sm.one_var([1, 2, 3, 4])
        approx(r["median"], 2.5)

    def test_single_element(self, sm):
        r = sm.one_var([42])
        assert r["n"] == 1
        assert r["mean_x"] == "42"
        assert r["sigma_x"] == "0"

    def test_empty_returns_error(self, sm):
        r = sm.one_var([])
        assert "error" in r

    def test_negative_values(self, sm):
        r = sm.one_var([-3, -1, -2])
        approx(r["mean_x"], -2)

    def test_floats(self, sm):
        r = sm.one_var([1.5, 2.5, 3.5])
        approx(r["mean_x"], 2.5)


# ── 2-variable statistics ─────────────────────────────────────────────────────

class TestTwoVar:
    def test_count(self, sm):
        r = sm.two_var([1, 2, 3], [4, 5, 6])
        assert r["n"] == 3

    def test_means(self, sm):
        r = sm.two_var([1, 2, 3], [10, 20, 30])
        approx(r["mean_x"], 2)
        approx(r["mean_y"], 20)

    def test_sum_xy(self, sm):
        r = sm.two_var([1, 2, 3], [4, 5, 6])
        # Σxy = 1×4 + 2×5 + 3×6 = 32
        assert r["sum_xy"] == "32"

    def test_mismatched_lengths(self, sm):
        r = sm.two_var([1, 2], [3])
        assert "error" in r

    def test_empty(self, sm):
        r = sm.two_var([], [])
        assert "error" in r


# ── Linear regression ─────────────────────────────────────────────────────────

class TestLinearRegression:
    def test_perfect_fit(self, sm):
        # y = 2x + 1
        x = [1, 2, 3, 4, 5]
        y = [3, 5, 7, 9, 11]
        r = sm.regression(x, y, "linear")
        approx(r["a"], 1)   # intercept
        approx(r["b"], 2)   # slope
        approx(r["r"], 1)   # perfect correlation

    def test_negative_slope(self, sm):
        x = [1, 2, 3, 4]
        y = [8, 6, 4, 2]
        r = sm.regression(x, y, "linear")
        approx(r["b"], -2)

    def test_r2_perfect(self, sm):
        x = [0, 1, 2, 3]
        y = [1, 3, 5, 7]
        r = sm.regression(x, y, "linear")
        approx(r["r2"], 1.0)

    def test_insufficient_data(self, sm):
        r = sm.regression([1], [2], "linear")
        assert "error" in r


# ── Quadratic regression ──────────────────────────────────────────────────────

class TestQuadraticRegression:
    def test_perfect_quadratic(self, sm):
        # y = x²
        x = [1, 2, 3, 4, 5]
        y = [1, 4, 9, 16, 25]
        r = sm.regression(x, y, "quadratic")
        assert "error" not in r
        approx(r["a"], 0)     # constant term ≈ 0
        approx(r["b"], 0)     # linear term ≈ 0
        approx(r["c"], 1)     # quadratic term ≈ 1

    def test_r2_present(self, sm):
        x = [1, 2, 3, 4, 5]
        y = [1, 4, 9, 16, 25]
        r = sm.regression(x, y, "quadratic")
        approx(r["r2"], 1.0)


# ── Logarithmic regression ────────────────────────────────────────────────────

class TestLogarithmicRegression:
    def test_basic(self, sm):
        import math
        x = [1, 2, 4, 8]
        y = [0, 1, 2, 3]   # y = log2(x) = ln(x)/ln(2)
        r = sm.regression(x, y, "logarithmic")
        assert "error" not in r
        approx(r["b"], 1 / math.log(2), rel=1e-4)

    def test_negative_x_returns_error(self, sm):
        r = sm.regression([-1, 1, 2], [1, 2, 3], "logarithmic")
        assert "error" in r


# ── Exponential regression ────────────────────────────────────────────────────

class TestExponentialRegression:
    def test_basic(self, sm):
        import math
        # y = 2 * e^(0.5x)
        x = [0, 1, 2, 3, 4]
        y = [2 * math.exp(0.5 * xi) for xi in x]
        r = sm.regression(x, y, "exponential")
        assert "error" not in r
        approx(r["a"], 2.0, rel=1e-4)
        approx(r["b"], 0.5, rel=1e-4)

    def test_negative_y_returns_error(self, sm):
        r = sm.regression([1, 2, 3], [-1, 2, 3], "exponential")
        assert "error" in r


# ── Power regression ──────────────────────────────────────────────────────────

class TestPowerRegression:
    def test_perfect_power(self, sm):
        # y = x^2
        x = [1, 2, 3, 4, 5]
        y = [1, 4, 9, 16, 25]
        r = sm.regression(x, y, "power")
        assert "error" not in r
        approx(r["a"], 1.0, rel=1e-4)
        approx(r["b"], 2.0, rel=1e-4)

    def test_negative_x_returns_error(self, sm):
        r = sm.regression([-1, 2, 3], [1, 4, 9], "power")
        assert "error" in r


# ── Unknown regression type ───────────────────────────────────────────────────

def test_unknown_regression_type(sm):
    r = sm.regression([1, 2, 3], [4, 5, 6], "cubic")
    assert "error" in r


# ── API endpoint tests ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_stat_one_var(client):
    resp = await client.post("/api/stat/one_var", json={"x": [1, 2, 3, 4, 5]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["n"] == 5
    assert "mean_x" in data


@pytest.mark.anyio
async def test_api_stat_two_var(client):
    resp = await client.post(
        "/api/stat/two_var", json={"x": [1, 2, 3], "y": [4, 5, 6]}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["n"] == 3


@pytest.mark.anyio
async def test_api_stat_regression(client):
    resp = await client.post(
        "/api/stat/regression",
        json={"x": [1, 2, 3, 4, 5], "y": [3, 5, 7, 9, 11], "type": "linear"},
    )
    assert resp.status_code == 200
    data = resp.json()
    approx(data["b"], 2)
