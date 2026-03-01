"""Tests for the Casio BASIC interpreter (Phase 6)."""

import os
import pytest
from app.calculator.modes.program import (
    CasioBasicInterpreter,
    parse_program,
    parse_stmt,
    build_jump_table,
    _eval,
    _eval_cond,
)

PROGRAMS_DIR = os.path.join(os.path.dirname(__file__), "basic_programs")


def _load(name: str) -> str:
    with open(os.path.join(PROGRAMS_DIR, name)) as f:
        return f.read()


def run(source: str, inputs=None):
    interp = CasioBasicInterpreter()
    return interp.run(source, inputs)


# ─────────────────────────────────────────────────────────────────────────────
# Expression evaluator
# ─────────────────────────────────────────────────────────────────────────────

class TestEval:
    def test_integer(self):
        assert _eval("2+3", {}) == 5.0

    def test_float(self):
        assert abs(_eval("1/3", {}) - 1/3) < 1e-9

    def test_variable(self):
        assert _eval("A+1", {"A": 4.0}) == 5.0

    def test_sqrt(self):
        assert abs(_eval("sqrt(4)", {}) - 2.0) < 1e-9

    def test_int_function(self):
        assert _eval("Int(3.7)", {}) == 3.0

    def test_frac_function(self):
        assert abs(_eval("Frac(3.7)", {}) - 0.7) < 1e-9

    def test_log(self):
        assert abs(_eval("log(100)", {}) - 2.0) < 1e-9

    def test_trig_deg(self):
        assert abs(_eval("sin(30)", {}, "DEG") - 0.5) < 1e-9
        assert abs(_eval("cos(60)", {}, "DEG") - 0.5) < 1e-9

    def test_nested_expr(self):
        # N - Int(N/A)*A = N mod A
        vars_ = {"N": 7.0, "A": 3.0}
        assert _eval("N-Int(N/A)*A", vars_) == 1.0   # 7 mod 3 = 1

    def test_error_raises(self):
        with pytest.raises(ValueError):
            _eval("1/0", {})


# ─────────────────────────────────────────────────────────────────────────────
# Condition evaluator
# ─────────────────────────────────────────────────────────────────────────────

class TestCond:
    def test_greater(self):
        assert _eval_cond("5>3", {}) is True
        assert _eval_cond("3>5", {}) is False

    def test_less(self):
        assert _eval_cond("2<4", {}) is True

    def test_equal(self):
        assert _eval_cond("A=5", {"A": 5.0}) is True
        assert _eval_cond("A=5", {"A": 6.0}) is False

    def test_gte(self):
        assert _eval_cond("5>=5", {}) is True
        assert _eval_cond("5>=6", {}) is False

    def test_lte(self):
        assert _eval_cond("3<=3", {}) is True
        assert _eval_cond("4<=3", {}) is False

    def test_neq(self):
        assert _eval_cond("3!=4", {}) is True
        assert _eval_cond("3!=3", {}) is False

    def test_numeric_truth(self):
        assert _eval_cond("1", {}) is True
        assert _eval_cond("0", {}) is False

    def test_expression_lhs(self):
        # N mod A = 0
        assert _eval_cond("N-Int(N/A)*A=0", {"N": 6.0, "A": 3.0}) is True
        assert _eval_cond("N-Int(N/A)*A=0", {"N": 7.0, "A": 3.0}) is False


# ─────────────────────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────────────────────

class TestParser:
    def test_assign(self):
        s = parse_stmt("A+1→B")
        assert s.cmd == "ASSIGN"
        assert s.args["expr"] == "A+1"
        assert s.args["var"] == "B"

    def test_assign_ascii(self):
        from app.calculator.modes.program import _normalise
        s = parse_stmt(_normalise("A+1->B"))
        assert s.cmd == "ASSIGN"

    def test_for(self):
        s = parse_stmt("For I=1 To 10 Step 2")
        assert s.cmd == "FOR"
        assert s.args["var"] == "I"
        assert s.args["start"] == "1"
        assert s.args["end"] == "10"
        assert s.args["step"] == "2"

    def test_for_no_step(self):
        s = parse_stmt("For I=1 To 5")
        assert s.args["step"] == "1"

    def test_next(self):
        s = parse_stmt("Next I")
        assert s.cmd == "NEXT"

    def test_while(self):
        s = parse_stmt("While A<10")
        assert s.cmd == "WHILE"
        assert s.args["cond"] == "A<10"

    def test_if_block(self):
        s = parse_stmt("If A>5")
        assert s.cmd == "IF_BLOCK"
        assert s.args["cond"] == "A>5"

    def test_if_inline(self):
        s = parse_stmt("If A>5 Then Print A")
        assert s.cmd == "IF_INLINE"
        assert s.args["then_stmt"].cmd == "PRINT_EXPR"

    def test_if_inline_assign(self):
        s = parse_stmt("If A>5 Then 0→P")
        assert s.cmd == "IF_INLINE"
        assert s.args["then_stmt"].cmd == "ASSIGN"

    def test_input(self):
        s = parse_stmt('Input "A=",A')
        assert s.cmd == "INPUT"
        assert s.args["var"] == "A"
        assert s.args["prompt"] == "A="

    def test_input_q(self):
        s = parse_stmt("?→A")
        assert s.cmd == "INPUT"
        assert s.args["var"] == "A"

    def test_print_str(self):
        s = parse_stmt('"Hello"')
        assert s.cmd == "PRINT_STR"
        assert s.args["text"] == "Hello"

    def test_print_expr(self):
        s = parse_stmt("Print A+1")
        assert s.cmd == "PRINT_EXPR"

    def test_goto(self):
        s = parse_stmt("Goto 1")
        assert s.cmd == "GOTO"
        assert s.args["label"] == "1"

    def test_lbl(self):
        s = parse_stmt("Lbl 1")
        assert s.cmd == "LBL"

    def test_locate(self):
        s = parse_stmt('Locate 1,2,"Hi"')
        assert s.cmd == "LOCATE"
        assert s.args["x"] == "1"
        assert s.args["y"] == "2"
        assert s.args["text"] == '"Hi"'

    def test_viewwindow(self):
        s = parse_stmt("ViewWindow -10,10,1,-5,5,1")
        assert s.cmd == "VIEWWINDOW"
        assert len(s.args["args"]) == 6

    def test_ploton(self):
        s = parse_stmt("PlotOn X,Y")
        assert s.cmd == "PLOTON"

    def test_stop(self):
        s = parse_stmt("Stop")
        assert s.cmd == "STOP"

    def test_return(self):
        s = parse_stmt("Return")
        assert s.cmd == "RETURN"

    def test_clrtext(self):
        s = parse_stmt("ClrText")
        assert s.cmd == "CLRTEXT"

    def test_clrgraph(self):
        s = parse_stmt("ClrGraph")
        assert s.cmd == "CLRGRAPH"

    def test_colon_split(self):
        stmts = parse_program('1->A:2->B')
        assert len(stmts) == 2
        assert stmts[0].args["var"] == "A"
        assert stmts[1].args["var"] == "B"


# ─────────────────────────────────────────────────────────────────────────────
# Jump table
# ─────────────────────────────────────────────────────────────────────────────

class TestJumpTable:
    def test_for_next(self):
        src = "For I=1 To 3\nPrint I\nNext I"
        stmts = parse_program(src)
        jt = build_jump_table(stmts)
        assert ("FOR_BODY", 0) in jt
        assert ("FOR_EXIT", 0) in jt

    def test_while_whileend(self):
        src = "While A<5\nA+1->A\nWhileEnd"
        stmts = parse_program(src)
        jt = build_jump_table(stmts)
        assert ("WHILE_EXIT", 0) in jt
        assert ("WHILEEND_TO", 2) in jt

    def test_if_ifend(self):
        src = "If A>5\nThen\nPrint A\nIfEnd"
        stmts = parse_program(src)
        jt = build_jump_table(stmts)
        assert ("IF_IFEND", 0) in jt

    def test_if_else_ifend(self):
        src = "If A>5\nThen\nPrint A\nElse\nPrint B\nIfEnd"
        stmts = parse_program(src)
        jt = build_jump_table(stmts)
        assert ("IF_ELSE", 0) in jt
        assert ("ELSE_IFEND", 3) in jt

    def test_labels(self):
        src = "Lbl 1\nPrint A\nGoto 1"
        stmts = parse_program(src)
        jt = build_jump_table(stmts)
        assert ("LBL", "1") in jt
        assert jt[("LBL", "1")] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Execution — basic operations
# ─────────────────────────────────────────────────────────────────────────────

class TestExecution:
    def test_assign_and_print(self):
        res = run("5->A\nPrint A")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "5" in texts

    def test_string_display(self):
        res = run('"Hello World"')
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "Hello World" in texts

    def test_arithmetic(self):
        res = run("3+4->A\nPrint A")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "7" in texts

    def test_for_loop(self):
        res = run("For I=1 To 3\nPrint I\nNext I")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == ["1", "2", "3"]

    def test_for_step_2(self):
        res = run("For I=1 To 9 Step 2\nPrint I\nNext I")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == ["1", "3", "5", "7", "9"]

    def test_for_step_negative(self):
        res = run("For I=5 To 1 Step -1\nPrint I\nNext I")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == ["5", "4", "3", "2", "1"]

    def test_for_skip_when_empty(self):
        res = run("For I=5 To 1\nPrint I\nNext I")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == []   # step=1, 5>1 so body never executes

    def test_while_loop(self):
        res = run("1->A\nWhile A<=3\nPrint A\nA+1->A\nWhileEnd")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == ["1", "2", "3"]

    def test_do_lpwhile(self):
        res = run("0->A\nDo\nA+1->A\nPrint A\nLpWhile A<3")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == ["1", "2", "3"]

    def test_if_block_true(self):
        res = run("5->A\nIf A>3\nThen\nPrint A\nIfEnd")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "5" in texts

    def test_if_block_false(self):
        res = run("2->A\nIf A>3\nThen\nPrint A\nIfEnd")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == []

    def test_if_else(self):
        res = run("2->A\nIf A>3\nThen\n\"big\"\nElse\n\"small\"\nIfEnd")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "small" in texts

    def test_if_inline_true(self):
        res = run("5->A\nIf A>3 Then Print A")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "5" in texts

    def test_if_inline_false(self):
        res = run("1->A\nIf A>3 Then Print A")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == []

    def test_if_inline_assign(self):
        res = run("1->P\n3->N\nIf N-Int(N/2)*2=0 Then 0->P\nPrint P")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == ["1"]   # 3 is odd, P stays 1

    def test_lbl_goto(self):
        res = run("0->A\nLbl 1\nA+1->A\nIf A<3 Then Goto 1\nPrint A")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == ["3"]

    def test_input_supplied(self):
        res = run('Input "A=",A\nInput "B=",B\nA+B->C\nPrint C', inputs=[3, 4])
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "7" in texts

    def test_input_needed_event(self):
        res = run('Input "X=",X\nPrint X')
        assert res.input_needed is True
        inp_events = [e for e in res.events if e["type"] == "input"]
        assert len(inp_events) == 1
        assert inp_events[0]["var"] == "X"

    def test_stop(self):
        res = run("Print 1\nStop\nPrint 2")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == ["1"]
        assert res.terminated is True

    def test_clrtext_event(self):
        res = run("ClrText")
        assert any(e["type"] == "clrtext" for e in res.events)

    def test_clrgraph_event(self):
        res = run("ClrGraph")
        assert any(e["type"] == "clrgraph" for e in res.events)

    def test_pause_event(self):
        res = run("◢")
        assert any(e["type"] == "pause" for e in res.events)

    def test_pause_ascii(self):
        res = run(">>")
        assert any(e["type"] == "pause" for e in res.events)

    def test_locate_event(self):
        res = run('Locate 1,1,"Hi"')
        loc = [e for e in res.events if e["type"] == "locate"]
        assert len(loc) == 1
        assert loc[0]["text"] == "Hi"

    def test_viewwindow(self):
        interp = CasioBasicInterpreter()
        interp.run("ViewWindow -5,5,1,-5,5,1")
        assert interp.view["xmin"] == -5.0
        assert interp.view["xmax"] == 5.0

    def test_ploton_event(self):
        res = run("ViewWindow -10,10,1,-10,10,1\nPlotOn 0,0")
        plots = [e for e in res.events if e["type"] == "plot"]
        assert len(plots) == 1
        assert plots[0]["cmd"] == "PLOTON"

    def test_graph_y_event(self):
        res = run("Graph Y=X*X")
        gy = [e for e in res.events if e["type"] == "graph_y"]
        assert len(gy) == 1
        assert gy[0]["expr"] == "X*X"

    def test_nested_for(self):
        res = run("For I=1 To 2\nFor J=1 To 2\nI*10+J->A\nPrint A\nNext J\nNext I")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert texts == ["11", "12", "21", "22"]

    def test_variable_persistence(self):
        res = run("5->A\n10->B\nA+B->C\nPrint C")
        assert res.variables["A"] == 5.0
        assert res.variables["B"] == 10.0
        assert res.variables["C"] == 15.0

    def test_ans_updated(self):
        res = run("3+4->A\nPrint A")
        assert res.variables["ANS"] == 7.0

    def test_colon_separator(self):
        res = run("1->A:2->B:A+B->C\nPrint C")
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "3" in texts

    def test_max_iterations_guard(self):
        # Infinite loop — should hit MAX_ITERATIONS and return an error
        res = run("Lbl 1\nGoto 1")
        assert res.error is not None

    def test_no_error_simple(self):
        res = run("1->A\nPrint A")
        assert res.error is None


# ─────────────────────────────────────────────────────────────────────────────
# Fixture programs
# ─────────────────────────────────────────────────────────────────────────────

class TestFixturePrograms:
    def test_fibonacci(self):
        src = _load("fibonacci.cas")
        res = run(src)
        assert res.error is None
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        # First 10 Fibonacci numbers: 0 1 1 2 3 5 8 13 21 34
        assert texts == ["0", "1", "1", "2", "3", "5", "8", "13", "21", "34"]

    def test_primes(self):
        src = _load("primes.cas")
        res = run(src)
        assert res.error is None
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        expected = ["2", "3", "5", "7", "11", "13", "17", "19", "23", "29",
                    "31", "37", "41", "43", "47"]
        assert texts == expected

    def test_quadratic_two_roots(self):
        src = _load("quadratic.cas")
        res = run(src, inputs=[1, -5, 6])   # x^2 - 5x + 6 = 0 → roots 3, 2
        assert res.error is None
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        floats = [float(t) for t in texts]
        assert sorted(floats) == pytest.approx([2.0, 3.0])

    def test_quadratic_no_real_roots(self):
        src = _load("quadratic.cas")
        res = run(src, inputs=[1, 0, 1])    # x^2 + 1 = 0, no real roots
        assert res.error is None
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "No real roots" in texts

    def test_input_test(self):
        src = _load("input_test.cas")
        res = run(src, inputs=[6, 4])       # A=6, B=4
        assert res.error is None
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        # sum=10, diff=2, product=24
        assert "10" in texts
        assert "2" in texts
        assert "24" in texts

    def test_bounce(self):
        src = _load("bounce.cas")
        res = run(src)
        assert res.error is None
        # Should have ClrGraph and PlotOn events
        assert any(e["type"] == "clrgraph" for e in res.events)
        assert any(e["type"] == "plot" for e in res.events)


# ─────────────────────────────────────────────────────────────────────────────
# Subroutines (Prog/Return)
# ─────────────────────────────────────────────────────────────────────────────

class TestSubroutines:
    def test_prog_call(self):
        interp = CasioBasicInterpreter()
        interp.programs["DOUBLE"] = '2*A->A'
        res = interp.run('5->A\nProg "DOUBLE"\nPrint A')
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "10" in texts

    def test_prog_not_found(self):
        res = run('Prog "MISSING"')
        assert res.error is not None

    def test_return_stops_subprog(self):
        interp = CasioBasicInterpreter()
        interp.programs["SUB"] = 'Print 1\nReturn\nPrint 2'
        res = interp.run('Prog "SUB"\nPrint 3')
        texts = [e["text"] for e in res.events if e["type"] == "text"]
        assert "1" in texts
        assert "2" not in texts
        assert "3" in texts
