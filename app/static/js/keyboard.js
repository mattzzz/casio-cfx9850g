/**
 * Casio CFX-9850G — Keyboard handler
 * Maps button clicks and physical keyboard presses → key events → WebSocket
 */

'use strict';

const Keyboard = (() => {
  let _onKey = null;   // callback(keyName)
  let shiftActive = false;
  let alphaActive = false;

  // Physical keyboard → calculator key mapping
  const KEY_MAP = {
    '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
    '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
    '.': 'DOT', '+': 'PLUS', '-': 'MINUS',
    '*': 'MUL', '/': 'DIV',
    '(': 'LPAREN', ')': 'RPAREN',
    '^': 'POW',
    'x': 'XTHETA', 'X': 'XTHETA',
    'Enter': 'EXE', 'Backspace': 'DEL', 'Escape': 'AC',
    'ArrowUp': 'UP', 'ArrowDown': 'DOWN',
    'ArrowLeft': 'LEFT', 'ArrowRight': 'RIGHT',
  };

  function _setShift(on) {
    shiftActive = on;
    const btn = document.getElementById('key-SHIFT');
    if (btn) btn.classList.toggle('active', on);
    document.body.classList.toggle('shift-active', on);
  }

  function _setAlpha(on) {
    alphaActive = on;
    const btn = document.getElementById('key-ALPHA');
    if (btn) btn.classList.toggle('active', on);
    document.body.classList.toggle('alpha-active', on);
  }

  function _fireKey(key) {
    if (key === 'SHIFT') {
      shiftActive = !shiftActive;
      _setShift(shiftActive);
      if (shiftActive) _setAlpha(false);
    } else if (key === 'ALPHA') {
      alphaActive = !alphaActive;
      _setAlpha(alphaActive);
      if (alphaActive) _setShift(false);
    } else {
      // Non-modifier: clear SHIFT/ALPHA after consumption (backend mirrors this)
      const toSend = key;
      if (toSend !== 'SHIFT' && toSend !== 'ALPHA') {
        _setShift(false);
        _setAlpha(false);
      }
    }
    if (_onKey) _onKey(key);
  }

  function _flash(btn) {
    btn.classList.add('pressed');
    setTimeout(() => btn.classList.remove('pressed'), 100);
  }

  function init(onKey) {
    _onKey = onKey;

    // Button clicks
    document.querySelectorAll('.key[data-key]').forEach(btn => {
      btn.addEventListener('click', () => {
        _flash(btn);
        _fireKey(btn.dataset.key);
      });
    });

    // Physical keyboard
    document.addEventListener('keydown', e => {
      const mapped = KEY_MAP[e.key];
      if (mapped) {
        e.preventDefault();
        const btn = document.querySelector(`.key[data-key="${mapped}"]`);
        if (btn) _flash(btn);
        _fireKey(mapped);
      }
    });
  }

  return { init };
})();
