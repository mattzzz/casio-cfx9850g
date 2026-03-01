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
    STAT:  ['1VAR', '2VAR', 'REG', '', '', ''],
    EQUA:  ['POLY', 'SIML', ';', '', '', ''],
    MAT:   ['A', 'B', 'C', 'D', 'E', 'F'],
    BASE:  ['DEC', 'HEX', 'BIN', 'OCT', '', ''],
    PRGM:  ['RUN', 'EDIT', 'NEW', 'LOAD', '', 'LIST'],
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
