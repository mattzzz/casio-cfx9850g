"""COMP mode tests — 80+ cases.

Tests the CalculatorEngine directly for speed and clarity.
All trig tests assume DEG mode (CFX-9850G factory default).
"""

import pytest
import math
from app.calculator.engine import CalculatorEngine
from app.calculator.modes.comp import CompMode


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def eng():
    return CalculatorEngine()


@pytest.fixture
def comp():
    return CompMode(CalculatorEngine())


# ── Helper ────────────────────────────────────────────────────────────────────

def approx_result(engine, expr, expected, rel=1e-6):
    """Evaluate expr and check it's close to expected (float)."""
    result = engine.evaluate(expr)
    assert "ERROR" not in result, f"Got error '{result}' for '{expr}'"
    assert float(result) == pytest.approx(float(expected), rel=rel), \
        f"'{expr}' → '{result}', expected ~{expected}"


# ── 1. Basic Arithmetic ───────────────────────────────────────────────────────

def test_add_integers(eng):         assert eng.evaluate("1+1") == "2"
def test_add_floats(eng):           approx_result(eng, "1.5+2.5", 4)
def test_subtract(eng):             assert eng.evaluate("10-3") == "7"
def test_multiply(eng):             assert eng.evaluate("6*7") == "42"
def test_divide_exact(eng):         assert eng.evaluate("10/2") == "5"
def test_divide_float(eng):         approx_result(eng, "1/3", 1/3)
def test_negative_result(eng):      assert eng.evaluate("3-10") == "-7"
def test_large_numbers(eng):        assert eng.evaluate("1000000*1000000") == "1000000000000"
def test_operator_precedence(eng):  assert eng.evaluate("2+3*4") == "14"
def test_parentheses(eng):          assert eng.evaluate("(2+3)*4") == "20"
def test_nested_parens(eng):        assert eng.evaluate("((2+3)*(4-1))") == "15"
def test_unary_minus_expr(eng):     assert eng.evaluate("(-5)+3") == "-2"
def test_decimal_arithmetic(eng):   approx_result(eng, "3.14*2", 6.28)
def test_chain_operations(eng):     assert eng.evaluate("1+2+3+4+5") == "15"
def test_modulo_via_expr(eng):      approx_result(eng, "10-3*3", 1)


# ── 2. Trig Functions — DEG mode ──────────────────────────────────────────────

def test_sin_0(eng):    approx_result(eng, "sin(0)", 0)
def test_sin_30(eng):   approx_result(eng, "sin(30)", 0.5)
def test_sin_45(eng):   approx_result(eng, "sin(45)", math.sin(math.radians(45)))
def test_sin_90(eng):   approx_result(eng, "sin(90)", 1)
def test_sin_180(eng):  approx_result(eng, "sin(180)", 0, rel=1e-5)
def test_cos_0(eng):    approx_result(eng, "cos(0)", 1)
def test_cos_60(eng):   approx_result(eng, "cos(60)", 0.5)
def test_cos_90(eng):   approx_result(eng, "cos(90)", 0, rel=1e-5)
def test_cos_180(eng):  approx_result(eng, "cos(180)", -1)
def test_tan_0(eng):    approx_result(eng, "tan(0)", 0)
def test_tan_45(eng):   approx_result(eng, "tan(45)", 1)
def test_tan_neg45(eng): approx_result(eng, "tan(-45)", -1)
def test_sin_neg90(eng): approx_result(eng, "sin(-90)", -1)


# ── 3. Inverse Trig — DEG mode ───────────────────────────────────────────────

def test_asin_half(eng):     approx_result(eng, "asin(0.5)", 30)
def test_asin_1(eng):        approx_result(eng, "asin(1)", 90)
def test_acos_half(eng):     approx_result(eng, "acos(0.5)", 60)
def test_acos_1(eng):        approx_result(eng, "acos(1)", 0)
def test_atan_1(eng):        approx_result(eng, "atan(1)", 45)
def test_atan_0(eng):        approx_result(eng, "atan(0)", 0)


# ── 4. RAD mode trig ─────────────────────────────────────────────────────────

def test_rad_sin_pi_over_2(eng):
    eng.set_angle_mode("RAD")
    approx_result(eng, "sin(pi/2)", 1)

def test_rad_cos_pi(eng):
    eng.set_angle_mode("RAD")
    approx_result(eng, "cos(pi)", -1)

def test_rad_asin_1(eng):
    eng.set_angle_mode("RAD")
    approx_result(eng, "asin(1)", math.pi/2)


# ── 5. log and ln ─────────────────────────────────────────────────────────────

def test_log_100(eng):        approx_result(eng, "log(100)", 2)
def test_log_1(eng):          approx_result(eng, "log(1)", 0)
def test_log_10(eng):         approx_result(eng, "log(10)", 1)
def test_log_1000(eng):       approx_result(eng, "log(1000)", 3)
def test_ln_e(eng):           approx_result(eng, "ln(e)", 1)
def test_ln_1(eng):           approx_result(eng, "ln(1)", 0)
def test_ln_e_squared(eng):   approx_result(eng, "ln(e**2)", 2)


# ── 6. Powers and roots ───────────────────────────────────────────────────────

def test_square(eng):         assert eng.evaluate("5**2") == "25"
def test_cube(eng):           assert eng.evaluate("2**3") == "8"
def test_power_xor(eng):      assert eng.evaluate("2^10") == "1024"
def test_sqrt_4(eng):         assert eng.evaluate("sqrt(4)") == "2"
def test_sqrt_9(eng):         assert eng.evaluate("sqrt(9)") == "3"
def test_sqrt_2(eng):         approx_result(eng, "sqrt(2)", math.sqrt(2))
def test_sqrt_0(eng):         assert eng.evaluate("sqrt(0)") == "0"
def test_pow_fraction(eng):   approx_result(eng, "4**0.5", 2)
def test_negative_pow(eng):   approx_result(eng, "2**(-1)", 0.5)
def test_inv(eng):            approx_result(eng, "4**(-1)", 0.25)


# ── 7. Complex numbers ────────────────────────────────────────────────────────

def test_sqrt_neg1(eng):
    r = eng.evaluate("sqrt(-1)")
    assert "i" in r and "ERROR" not in r

def test_sqrt_neg4(eng):
    r = eng.evaluate("sqrt(-4)")
    assert "2i" in r and "ERROR" not in r

def test_complex_add(eng):
    r = eng.evaluate("(1+2*i)+(3+4*i)")
    assert "4" in r and "6" in r and "i" in r

def test_imaginary_unit(eng):
    r = eng.evaluate("i**2")
    assert r == "-1"

def test_complex_output_format(eng):
    r = eng.evaluate("sqrt(-1)")
    assert "j" not in r, "Should use 'i' not 'j'"


# ── 8. Variables A–Z ──────────────────────────────────────────────────────────

def test_store_and_recall_A(eng):
    eng.store_variable("A", "42")
    assert eng.evaluate("A") == "42"

def test_store_expression(eng):
    eng.store_variable("B", "3+4")
    assert eng.evaluate("B") == "7"

def test_use_variable_in_expr(eng):
    eng.store_variable("X", "5")
    assert eng.evaluate("X*X") == "25"

def test_variable_default_zero(eng):
    assert eng.evaluate("Z") == "0"

def test_store_multiple(eng):
    eng.store_variable("A", "3")
    eng.store_variable("B", "4")
    assert eng.evaluate("A**2+B**2") == "25"


# ── 9. Ans register ───────────────────────────────────────────────────────────

def test_ans_stored_after_eval(eng):
    eng.evaluate("6*7")
    assert eng.evaluate("Ans") == "42"

def test_ans_used_in_expression(eng):
    eng.evaluate("10")
    approx_result(eng, "Ans+5", 15)

def test_ans_updated_each_eval(eng):
    eng.evaluate("5")       # Ans = 5
    eng.evaluate("Ans*2")   # Ans = 10
    assert eng.evaluate("Ans") == "10"

def test_ans_not_updated_on_error(eng):
    eng.evaluate("10")
    eng.evaluate("1/0")   # error — Ans should stay 10
    assert eng.evaluate("Ans") == "10"


# ── 10. Error Handling ────────────────────────────────────────────────────────

def test_div_by_zero(eng):
    assert eng.evaluate("1/0") == "Math ERROR"

def test_div_by_zero_expr(eng):
    assert eng.evaluate("sin(0)/0") == "Math ERROR"

def test_syntax_error(eng):
    # Expression with no operands between operators
    assert eng.evaluate("1*/2") == "Syntax ERROR"

def test_empty_expr(eng):
    assert eng.evaluate("") == ""

def test_unmatched_paren(eng):
    result = eng.evaluate("(1+2")
    assert "ERROR" in result

def test_log_zero(eng):
    assert eng.evaluate("log(0)") == "Math ERROR"

def test_ln_zero(eng):
    assert eng.evaluate("ln(0)") == "Math ERROR"

def test_log_negative(eng):
    # ln(-1) = iπ — valid complex result in CFX mode
    r = eng.evaluate("ln(-1)")
    assert "ERROR" not in r   # complex result allowed


# ── 11. Edge Cases ────────────────────────────────────────────────────────────

def test_zero(eng):         assert eng.evaluate("0") == "0"
def test_pi_constant(eng):  approx_result(eng, "pi", math.pi)
def test_e_constant(eng):   approx_result(eng, "e", math.e)
def test_implicit_mul_pi(eng):
    approx_result(eng, "2*pi", 2*math.pi)

def test_large_exponent(eng):
    # 10^99 is just at the edge of overflow
    r = eng.evaluate("10**99")
    assert "ERROR" not in r

def test_overflow(eng):
    r = eng.evaluate("10**100")
    assert "ERROR" in r

def test_sin_compound(eng):
    # sin²(x) + cos²(x) = 1
    approx_result(eng, "sin(30)**2 + cos(30)**2", 1)

def test_negative_sqrt_is_complex(eng):
    r = eng.evaluate("sqrt(-9)")
    assert "3" in r and "i" in r


# ── 12. CompMode state machine ────────────────────────────────────────────────

def test_comp_digit_append(comp):
    comp.handle_key("1")
    comp.handle_key("2")
    comp.handle_key("3")
    state = comp.handle_key("EXE")
    assert state["result"] == "123"

def test_comp_ac_clears(comp):
    comp.handle_key("5")
    comp.handle_key("AC")
    state = comp.handle_key("EXE")
    assert state["expression"] == ""

def test_comp_del_removes_last(comp):
    comp.handle_key("5")
    comp.handle_key("6")
    comp.handle_key("DEL")
    assert comp.state.expression == "5"

def test_comp_shift_toggles(comp):
    state = comp.handle_key("SHIFT")
    assert state["shift"] is True
    state = comp.handle_key("SHIFT")
    assert state["shift"] is False

def test_comp_alpha_toggles(comp):
    state = comp.handle_key("ALPHA")
    assert state["alpha"] is True

def test_comp_shift_clears_alpha(comp):
    comp.handle_key("ALPHA")
    state = comp.handle_key("SHIFT")
    assert state["alpha"] is False
    assert state["shift"] is True

def test_comp_exe_evaluates(comp):
    comp.handle_key("2")
    comp.handle_key("PLUS")
    comp.handle_key("2")
    state = comp.handle_key("EXE")
    assert state["result"] == "4"
    assert state["error"] == ""

def test_comp_error_shown(comp):
    comp.handle_key("1")
    comp.handle_key("DIV")
    comp.handle_key("0")
    state = comp.handle_key("EXE")
    assert "ERROR" in state["error"]
    assert state["result"] == ""

def test_comp_angle_mode_change(comp):
    state = comp.handle_key("RAD")
    assert state["angle"] == "RAD"

def test_comp_shift_sin_is_asin(comp):
    comp.handle_key("SHIFT")
    state = comp.handle_key("SIN")
    assert "asin" in comp.state.expression
