/**
 * Casio CFX-9850G — Mode management + Softkey definitions
 *
 * SOFTKEYS: the 6 labels displayed in the LCD softkey bar per mode.
 * Each entry maps to F1..F6 respectively.
 */

'use strict';

const Modes = (() => {
  let currentMode = 'MENU';

  // ── Softkey label sets per mode ──────────────────────────────────────────
  // Verified against CFX-9850G manual conventions.
  const SOFTKEYS = {
    MENU:  ['', '', '', '', '', ''],
    COMP:  ['', '', '', '', '', ''],
    GRAPH: ['Y=', 'WIN', 'ZOOM', 'TRCE', '', 'DRAW'],
    TABLE: ['FORM', 'RNG', 'TABL', 'GPLT', '', ''],
    STAT:  ['GRPH', 'CALC', 'TEST', 'INTR', 'DIST', ''],
    EQUA:  ['SIML', 'POLY', '', '', '', ''],
    MAT:   ['', '', '', '', '', ''],
    BASE:  ['DEC', 'HEX', 'BIN', 'OCT', '', ''],
    PRGM:  ['', 'EDIT', 'NEW', '', '', ''],
    DYNA:  ['', '', '', '', '', ''],
    RECR:  ['', '', '', '', '', ''],
  };

  function setMode(mode) {
    currentMode = mode;
  }

  function getMode() {
    return currentMode;
  }

  // Return softkey labels for a given mode (defaults to empty array).
  function getSoftkeys(mode) {
    return (SOFTKEYS[mode] || ['', '', '', '', '', '']).slice();
  }

  return { setMode, getMode, getSoftkeys, SOFTKEYS };
})();
