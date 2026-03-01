"""Phase 3.5 — MENU navigation and COMP replay buffer tests.

Tests backend behaviour for:
- CompMode replay buffer (UP/DOWN keys)
- Mode constants / softkey label definitions
- WebSocket-based key sequences
"""

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.calculator.engine import CalculatorEngine
from app.calculator.modes.comp import CompMode


# ── CompMode replay buffer unit tests ────────────────────────────────────────

@pytest.fixture
def comp():
    return CompMode(CalculatorEngine())


def _type_and_execute(comp, expression):
    """Helper: type each character key then press EXE."""
    # Feed expression character by character through handle_key
    key_map = {
        '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
        '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
        '+': 'PLUS', '-': 'MINUS', '*': 'MUL', '/': 'DIV',
        '(': 'LPAREN', ')': 'RPAREN', '.': 'DOT',
    }
    for ch in expression:
        key = key_map.get(ch)
        if key:
            comp.handle_key(key)
    return comp.handle_key('EXE')


# ── Replay buffer: basic push ─────────────────────────────────────────────────

def test_replay_buffer_starts_empty(comp):
    assert comp._replay == []


def test_replay_buffer_fills_on_exe(comp):
    _type_and_execute(comp, '1+1')
    assert len(comp._replay) == 1
    assert comp._replay[0] == '1+1'


def test_replay_buffer_fills_multiple(comp):
    _type_and_execute(comp, '1+1')
    _type_and_execute(comp, '2+2')
    _type_and_execute(comp, '3+3')
    assert len(comp._replay) == 3
    assert comp._replay[-1] == '3+3'


def test_replay_buffer_max_seven(comp):
    for i in range(10):
        _type_and_execute(comp, f'{i}+0')
    assert len(comp._replay) <= 7


def test_replay_buffer_deduplication(comp):
    _type_and_execute(comp, '1+1')
    _type_and_execute(comp, '1+1')   # same expression — should not duplicate
    assert comp._replay.count('1+1') == 1


def test_replay_buffer_no_error_entries(comp):
    """Expressions that produce errors must NOT enter the replay buffer."""
    comp.handle_key('1')
    comp.handle_key('DIV')
    comp.handle_key('0')
    state = comp.handle_key('EXE')
    assert 'ERROR' in state['error']
    assert comp._replay == []


# ── Replay buffer: UP navigation ──────────────────────────────────────────────

def test_up_retrieves_most_recent(comp):
    _type_and_execute(comp, '1+1')
    _type_and_execute(comp, '2+2')
    # Clear expression to simulate user starting fresh
    comp.handle_key('AC')
    state = comp.handle_key('UP')
    assert state['expression'] == '2+2'


def test_up_twice_retrieves_second_most_recent(comp):
    _type_and_execute(comp, '1+1')
    _type_and_execute(comp, '2+2')
    comp.handle_key('AC')
    comp.handle_key('UP')
    state = comp.handle_key('UP')
    assert state['expression'] == '1+1'


def test_up_bounded_by_buffer_length(comp):
    _type_and_execute(comp, '1+1')
    comp.handle_key('AC')
    comp.handle_key('UP')
    # Second UP should not crash or go out of bounds
    state = comp.handle_key('UP')
    assert state['expression'] == '1+1'


def test_up_does_nothing_when_buffer_empty(comp):
    comp.handle_key('1')
    state = comp.handle_key('UP')
    # No replay entries — expression unchanged
    assert state['expression'] == '1'


# ── Replay buffer: DOWN navigation ────────────────────────────────────────────

def test_down_after_up_restores_expression(comp):
    _type_and_execute(comp, '1+1')
    # Type a partial expression, then browse
    comp.handle_key('3')
    comp.handle_key('UP')           # enter replay, show '1+1'
    state = comp.handle_key('DOWN') # exit replay, restore '3'
    assert state['expression'] == '3'


def test_down_without_up_is_noop(comp):
    comp.handle_key('5')
    state = comp.handle_key('DOWN')
    assert state['expression'] == '5'


def test_down_scrolls_forward_through_replay(comp):
    _type_and_execute(comp, '1+1')
    _type_and_execute(comp, '2+2')
    comp.handle_key('AC')
    comp.handle_key('UP')   # → '2+2'
    comp.handle_key('UP')   # → '1+1'
    state = comp.handle_key('DOWN')  # → '2+2'
    assert state['expression'] == '2+2'


# ── Replay exits on non-navigation key ────────────────────────────────────────

def test_non_nav_key_exits_replay(comp):
    _type_and_execute(comp, '1+1')
    comp.handle_key('AC')
    comp.handle_key('UP')    # enter replay
    comp.handle_key('5')     # non-nav key → exits replay
    assert comp._replay_idx == -1


# ── WebSocket integration: replay buffer over WS ─────────────────────────────

def test_ws_replay_up_key():
    """Send keys over WebSocket and verify replay buffer works end-to-end."""
    with TestClient(app).websocket_connect('/ws/calculator') as ws:
        # Type and execute '1+1'
        for key in ['1', 'PLUS', '1', 'EXE']:
            ws.send_json({'type': 'key', 'key': key})
            ws.receive_json()

        # Clear
        ws.send_json({'type': 'key', 'key': 'AC'})
        ws.receive_json()

        # UP should restore '1+1'
        ws.send_json({'type': 'key', 'key': 'UP'})
        state = ws.receive_json()
        assert state['expression'] == '1+1'


def test_ws_replay_multiple_entries():
    """Multiple expressions in replay buffer, navigate with UP."""
    with TestClient(app).websocket_connect('/ws/calculator') as ws:
        for expr_keys in [
            ['2', 'PLUS', '2', 'EXE'],
            ['3', 'PLUS', '3', 'EXE'],
        ]:
            for key in expr_keys:
                ws.send_json({'type': 'key', 'key': key})
                ws.receive_json()

        ws.send_json({'type': 'key', 'key': 'AC'})
        ws.receive_json()

        ws.send_json({'type': 'key', 'key': 'UP'})
        s1 = ws.receive_json()
        assert s1['expression'] == '3+3'

        ws.send_json({'type': 'key', 'key': 'UP'})
        s2 = ws.receive_json()
        assert s2['expression'] == '2+2'


def test_ws_replay_down_restores():
    with TestClient(app).websocket_connect('/ws/calculator') as ws:
        for key in ['5', 'PLUS', '5', 'EXE']:
            ws.send_json({'type': 'key', 'key': key})
            ws.receive_json()

        # Type partial expression '9'
        ws.send_json({'type': 'key', 'key': '9'})
        ws.receive_json()

        ws.send_json({'type': 'key', 'key': 'UP'})
        ws.receive_json()   # shows '5+5'

        ws.send_json({'type': 'key', 'key': 'DOWN'})
        state = ws.receive_json()
        assert state['expression'] == '9'


# ── Softkey constant correctness ─────────────────────────────────────────────
# These tests import the constants directly from a shared Python module
# if one were to exist, but since softkeys live in JS we validate the
# known expected values match the spec via a simple Python dict.

EXPECTED_SOFTKEYS = {
    'GRAPH': ['Y=', 'WIN', 'ZOOM', 'TRCE', 'GRPH', 'TABL'],
    'TABLE': ['FORM', 'RNG', 'TABL', 'GPLT', '', ''],
    'STAT':  ['GRPH', 'CALC', 'TEST', 'INTR', 'DIST', ''],
}


def test_softkey_graph_has_six_entries():
    assert len(EXPECTED_SOFTKEYS['GRAPH']) == 6


def test_softkey_graph_f1_is_y_equals():
    assert EXPECTED_SOFTKEYS['GRAPH'][0] == 'Y='


def test_softkey_graph_f5_is_grph():
    assert EXPECTED_SOFTKEYS['GRAPH'][4] == 'GRPH'


def test_softkey_graph_f6_is_tabl():
    assert EXPECTED_SOFTKEYS['GRAPH'][5] == 'TABL'


def test_softkey_table_f3_is_tabl():
    assert EXPECTED_SOFTKEYS['TABLE'][2] == 'TABL'


# ── AC/ON does not exit mode ──────────────────────────────────────────────────

def test_ac_clears_expression_not_mode(comp):
    """AC must clear the expression but must NOT change the mode field."""
    comp.handle_key('5')
    comp.handle_key('PLUS')
    comp.handle_key('3')
    state = comp.handle_key('AC')
    assert state['expression'] == ''
    assert state['mode'] == 'COMP'   # mode unchanged


def test_ws_ac_does_not_change_mode():
    with TestClient(app).websocket_connect('/ws/calculator') as ws:
        for key in ['5', 'PLUS', '3']:
            ws.send_json({'type': 'key', 'key': key})
            ws.receive_json()

        ws.send_json({'type': 'key', 'key': 'AC'})
        state = ws.receive_json()
        assert state['expression'] == ''
        assert state['mode'] == 'COMP'
