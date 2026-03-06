/**
 * Casio CFX-9850G — LCD Canvas Renderer
 * Physical LCD: 128×64 pixels  |  Rendered at 3× = 384×192 px
 *
 * Color zones:
 *   Rows  0– 7 (px  0–23)  → status bar  (orange-mode pixels)
 *   Rows  8–55 (px 24–167) → main area   (blue-mode pixels)
 *   Rows 56–63 (px 168–191)→ softkey bar  (green-mode pixels)
 *
 * Pixel colors per zone:
 *   status  : on=#b84800  off=#a8b84b
 *   main    : on=#1c2314  off=#a8b84b
 *   softkey : on=#004d1a  off=#a8b84b
 */

'use strict';

const LCD = (() => {
  const W = 128, H = 64, SCALE = 3;
  const PW = W * SCALE, PH = H * SCALE;   // canvas pixel dimensions

  // Pixel-on colours per zone
  const COL_OFF    = '#a8b84b';
  const COL_STATUS = '#b84800';   // orange
  const COL_MAIN   = '#1c2314';   // blue/dark
  const COL_SOFT   = '#004d1a';   // green

  // Pixel buffer: 1 = on, 0 = off  (128 × 64)
  const buf = new Uint8Array(W * H);

  let canvas, ctx;

  // ── 5×7 bitmap font (column-encoded, ASCII 0x20–0x7E) ──────────────────
  // Each char: 5 bytes = 5 columns. Bit 0 = top row, bit 6 = bottom row.
  // Standard Adafruit/Arduino 5×7 font data.
  const FONT = [
    [0x00,0x00,0x00,0x00,0x00], // 0x20 ' '
    [0x00,0x00,0x5F,0x00,0x00], // 0x21 '!'
    [0x00,0x07,0x00,0x07,0x00], // 0x22 '"'
    [0x14,0x7F,0x14,0x7F,0x14], // 0x23 '#'
    [0x24,0x2A,0x7F,0x2A,0x12], // 0x24 '$'
    [0x23,0x13,0x08,0x64,0x62], // 0x25 '%'
    [0x36,0x49,0x55,0x22,0x50], // 0x26 '&'
    [0x00,0x05,0x03,0x00,0x00], // 0x27 "'"
    [0x00,0x1C,0x22,0x41,0x00], // 0x28 '('
    [0x00,0x41,0x22,0x1C,0x00], // 0x29 ')'
    [0x08,0x2A,0x1C,0x2A,0x08], // 0x2A '*'
    [0x08,0x08,0x3E,0x08,0x08], // 0x2B '+'
    [0x00,0x50,0x30,0x00,0x00], // 0x2C ','
    [0x08,0x08,0x08,0x08,0x08], // 0x2D '-'
    [0x00,0x60,0x60,0x00,0x00], // 0x2E '.'
    [0x20,0x10,0x08,0x04,0x02], // 0x2F '/'
    [0x3E,0x51,0x49,0x45,0x3E], // 0x30 '0'
    [0x00,0x42,0x7F,0x40,0x00], // 0x31 '1'
    [0x42,0x61,0x51,0x49,0x46], // 0x32 '2'
    [0x21,0x41,0x45,0x4B,0x31], // 0x33 '3'
    [0x18,0x14,0x12,0x7F,0x10], // 0x34 '4'
    [0x27,0x45,0x45,0x45,0x39], // 0x35 '5'
    [0x3C,0x4A,0x49,0x49,0x30], // 0x36 '6'
    [0x01,0x71,0x09,0x05,0x03], // 0x37 '7'
    [0x36,0x49,0x49,0x49,0x36], // 0x38 '8'
    [0x06,0x49,0x49,0x29,0x1E], // 0x39 '9'
    [0x00,0x36,0x36,0x00,0x00], // 0x3A ':'
    [0x00,0x56,0x36,0x00,0x00], // 0x3B ';'
    [0x00,0x08,0x14,0x22,0x41], // 0x3C '<'
    [0x14,0x14,0x14,0x14,0x14], // 0x3D '='
    [0x41,0x22,0x14,0x08,0x00], // 0x3E '>'
    [0x02,0x01,0x51,0x09,0x06], // 0x3F '?'
    [0x32,0x49,0x79,0x41,0x3E], // 0x40 '@'
    [0x7E,0x11,0x11,0x11,0x7E], // 0x41 'A'
    [0x7F,0x49,0x49,0x49,0x36], // 0x42 'B'
    [0x3E,0x41,0x41,0x41,0x22], // 0x43 'C'
    [0x7F,0x41,0x41,0x22,0x1C], // 0x44 'D'
    [0x7F,0x49,0x49,0x49,0x41], // 0x45 'E'
    [0x7F,0x09,0x09,0x09,0x01], // 0x46 'F'
    [0x3E,0x41,0x49,0x49,0x7A], // 0x47 'G'
    [0x7F,0x08,0x08,0x08,0x7F], // 0x48 'H'
    [0x00,0x41,0x7F,0x41,0x00], // 0x49 'I'
    [0x20,0x40,0x41,0x3F,0x01], // 0x4A 'J'
    [0x7F,0x08,0x14,0x22,0x41], // 0x4B 'K'
    [0x7F,0x40,0x40,0x40,0x40], // 0x4C 'L'
    [0x7F,0x02,0x04,0x02,0x7F], // 0x4D 'M'
    [0x7F,0x04,0x08,0x10,0x7F], // 0x4E 'N'
    [0x3E,0x41,0x41,0x41,0x3E], // 0x4F 'O'
    [0x7F,0x09,0x09,0x09,0x06], // 0x50 'P'
    [0x3E,0x41,0x51,0x21,0x5E], // 0x51 'Q'
    [0x7F,0x09,0x19,0x29,0x46], // 0x52 'R'
    [0x46,0x49,0x49,0x49,0x31], // 0x53 'S'
    [0x01,0x01,0x7F,0x01,0x01], // 0x54 'T'
    [0x3F,0x40,0x40,0x40,0x3F], // 0x55 'U'
    [0x1F,0x20,0x40,0x20,0x1F], // 0x56 'V'
    [0x3F,0x40,0x38,0x40,0x3F], // 0x57 'W'
    [0x63,0x14,0x08,0x14,0x63], // 0x58 'X'
    [0x07,0x08,0x70,0x08,0x07], // 0x59 'Y'
    [0x61,0x51,0x49,0x45,0x43], // 0x5A 'Z'
    [0x00,0x7F,0x41,0x41,0x00], // 0x5B '['
    [0x02,0x04,0x08,0x10,0x20], // 0x5C '\'
    [0x00,0x41,0x41,0x7F,0x00], // 0x5D ']'
    [0x04,0x02,0x01,0x02,0x04], // 0x5E '^'
    [0x40,0x40,0x40,0x40,0x40], // 0x5F '_'
    [0x00,0x01,0x02,0x04,0x00], // 0x60 '`'
    [0x20,0x54,0x54,0x54,0x78], // 0x61 'a'
    [0x7F,0x48,0x44,0x44,0x38], // 0x62 'b'
    [0x38,0x44,0x44,0x44,0x20], // 0x63 'c'
    [0x38,0x44,0x44,0x48,0x7F], // 0x64 'd'
    [0x38,0x54,0x54,0x54,0x18], // 0x65 'e'
    [0x08,0x7E,0x09,0x01,0x02], // 0x66 'f'
    [0x08,0x54,0x54,0x54,0x3C], // 0x67 'g'
    [0x7F,0x08,0x04,0x04,0x78], // 0x68 'h'
    [0x00,0x44,0x7D,0x40,0x00], // 0x69 'i'
    [0x20,0x40,0x44,0x3D,0x00], // 0x6A 'j'
    [0x7F,0x10,0x28,0x44,0x00], // 0x6B 'k'
    [0x00,0x41,0x7F,0x40,0x00], // 0x6C 'l'
    [0x7C,0x04,0x18,0x04,0x7C], // 0x6D 'm'
    [0x7C,0x08,0x04,0x04,0x78], // 0x6E 'n'
    [0x38,0x44,0x44,0x44,0x38], // 0x6F 'o'
    [0x7C,0x14,0x14,0x14,0x08], // 0x70 'p'
    [0x08,0x14,0x14,0x18,0x7C], // 0x71 'q'
    [0x7C,0x08,0x04,0x04,0x08], // 0x72 'r'
    [0x48,0x54,0x54,0x54,0x20], // 0x73 's'
    [0x04,0x3F,0x44,0x40,0x20], // 0x74 't'
    [0x3C,0x40,0x40,0x20,0x7C], // 0x75 'u'
    [0x1C,0x20,0x40,0x20,0x1C], // 0x76 'v'
    [0x3C,0x40,0x30,0x40,0x3C], // 0x77 'w'
    [0x44,0x28,0x10,0x28,0x44], // 0x78 'x'
    [0x0C,0x50,0x50,0x50,0x3C], // 0x79 'y'
    [0x44,0x64,0x54,0x4C,0x44], // 0x7A 'z'
    [0x00,0x08,0x36,0x41,0x00], // 0x7B '{'
    [0x00,0x00,0x7F,0x00,0x00], // 0x7C '|'
    [0x00,0x41,0x36,0x08,0x00], // 0x7D '}'
    [0x08,0x04,0x08,0x10,0x08], // 0x7E '~' (reused as right-arrow)
  ];

  // ── pixel helpers ─────────────────────────────────────────────────────────

  function setPixel(x, y, on) {
    if (x < 0 || x >= W || y < 0 || y >= H) return;
    buf[y * W + x] = on ? 1 : 0;
  }

  function drawChar(ch, col, row) {
    // col/row in LCD pixel coords (not canvas pixels)
    const code = ch.charCodeAt(0);
    if (code < 0x20 || code > 0x7E) return;
    const glyph = FONT[code - 0x20];
    for (let cx = 0; cx < 5; cx++) {
      const colByte = glyph[cx];
      for (let cy = 0; cy < 7; cy++) {
        setPixel(col + cx, row + cy, (colByte >> cy) & 1);
      }
    }
  }

  function drawText(text, col, row) {
    let x = col;
    for (const ch of text) {
      drawChar(ch, x, row);
      x += 6;  // 5px char + 1px gap
    }
  }

  // ── draw a hollow rectangle border ────────────────────────────────────────
  function drawRect(x, y, w, h) {
    for (let i = x; i < x + w; i++) {
      setPixel(i, y, 1);
      setPixel(i, y + h - 1, 1);
    }
    for (let j = y + 1; j < y + h - 1; j++) {
      setPixel(x, j, 1);
      setPixel(x + w - 1, j, 1);
    }
  }

  // ── zone colour ───────────────────────────────────────────────────────────

  function pixelColour(x, y, on) {
    if (!on) return COL_OFF;
    if (y < 8)  return COL_STATUS;
    if (y >= 56) return COL_SOFT;
    return COL_MAIN;
  }

  // ── render buffer → canvas ────────────────────────────────────────────────

  function flush() {
    const img = ctx.createImageData(PW, PH);
    const d = img.data;
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const on = buf[y * W + x];
        const hex = pixelColour(x, y, on);
        const r = parseInt(hex.slice(1,3),16);
        const g = parseInt(hex.slice(3,5),16);
        const b = parseInt(hex.slice(5,7),16);
        for (let sy = 0; sy < SCALE; sy++) {
          for (let sx = 0; sx < SCALE; sx++) {
            const pi = ((y*SCALE+sy)*PW + (x*SCALE+sx)) * 4;
            d[pi]=r; d[pi+1]=g; d[pi+2]=b; d[pi+3]=255;
          }
        }
      }
    }
    ctx.putImageData(img, 0, 0);
  }

  // ── persistent softkey labels ─────────────────────────────────────────────
  let _softkeys = ['', '', '', '', '', ''];

  function setSoftkeys(labels) {
    _softkeys = (labels || ['', '', '', '', '', '']).slice(0, 6);
    // Pad to 6 if needed
    while (_softkeys.length < 6) _softkeys.push('');
  }

  // ── public: draw display state ────────────────────────────────────────────

  function render(state) {
    // Clear buffer
    buf.fill(0);

    const { expression='', result='', error='', mode='COMP',
            angle='DEG', shift=false, alpha=false,
            softkeys=null } = state;

    // If caller passes explicit softkeys, update persistent set
    if (softkeys) setSoftkeys(softkeys);

    // ── Status bar (rows 0–7) ────────────────────────────────────────────
    const statusLine =
      mode.padEnd(6) +
      angle.padEnd(5) +
      (shift ? 'S' : ' ') +
      (alpha ? 'A' : ' ');
    drawText(statusLine, 0, 0);

    // ── Expression area (rows 8–39, 4 LCD text rows of 8px each) ─────────
    const expLines = wrapText(expression, 21);
    for (let i = 0; i < Math.min(expLines.length, 4); i++) {
      drawText(expLines[i], 0, 9 + i * 8);
    }

    // ── Result (right-aligned, rows 40–55) ────────────────────────────────
    const displayResult = error || result;
    if (displayResult) {
      const trimmed = displayResult.slice(0, 21);
      const x = Math.max(0, (W - trimmed.length * 6));
      drawText(trimmed, x, 45);
    }

    // ── Softkey bar (rows 56–63) ──────────────────────────────────────────
    _drawSoftkeyBar(_softkeys);

    flush();
  }

  // Draw 6 softkey labels evenly spaced in the softkey zone (rows 56-63).
  // Each slot is ~21px wide; labels are truncated to 4 chars.
  function _drawSoftkeyBar(labels) {
    const slotW = Math.floor(W / 6);  // 21
    for (let i = 0; i < 6; i++) {
      const lbl = (labels[i] || '').slice(0, 4);
      if (lbl) drawText(lbl, i * slotW + 1, 57);
    }
  }

  // ── public: render the MAIN MENU — 3×3 icon grid ────────────────────────
  // Matches the CFX-9850G MAIN MENU layout: 3 columns × 3 rows of boxed icons.
  // Cell geometry: 40×16px per cell (3×40 + 2×1gap = 122px; 3×16 = 48px = main area)
  function renderMenu() {
    buf.fill(0);

    // Status bar
    drawText('MAIN MENU', 0, 0);

    // 9 cells (3 cols × 3 rows) — CFX-9850G standard layout
    const ITEMS = [
      ['1','RUN' ], ['2','STAT'], ['3','GRPH'],
      ['4','DYNA'], ['5','TABL'], ['6','RECR'],
      ['7','EQUA'], ['8','PRGM'], ['9','MAT' ],
    ];

    const CW = 40, CH = 16; // cell width / height in LCD pixels
    const GAP = 1;           // 1px gap between columns
    // interior width = CW - 2 = 38px

    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 3; c++) {
        const [num, lbl] = ITEMS[r * 3 + c];
        const x = c * (CW + GAP);   // 0, 41, 82
        const y = 8 + r * CH;        // 8, 24, 40

        // Border box
        drawRect(x, y, CW, CH);

        // Mode number — centred in 38px interior (single 5px char → offset 17)
        drawText(num, x + 17, y + 2);

        // Mode name — centred by character count
        const name = lbl.slice(0, 4);
        const nameX = x + 1 + Math.floor((38 - name.length * 6) / 2);
        drawText(name, nameX, y + 9);
      }
    }

    flush();
  }

  function wrapText(text, maxCols) {
    if (!text) return [''];
    const lines = [];
    for (let i = 0; i < text.length; i += maxCols) {
      lines.push(text.slice(i, i + maxCols));
    }
    return lines;
  }

  // ── public: render an external 128×64 pixel buffer ────────────────────────
  // extBuf: Array or Uint8Array of 8192 values (0=off, 1=on)
  // After loading the pixels, the softkey bar is redrawn on top so the
  // user can still read the F-key labels while viewing a graph.
  function renderPixelMap(extBuf) {
    const len = Math.min(extBuf.length, W * H);
    for (let i = 0; i < len; i++) buf[i] = extBuf[i] ? 1 : 0;
    // Redraw softkeys so they stay readable over graph area
    _drawSoftkeyBar(_softkeys);
    flush();
  }

  // ── public: render a value table as dot-matrix text ───────────────────────
  // rows: [{x: "...", y: "..."|undefined}, ...]
  // scrollOffset: first row index to display
  // Displays a header + up to 5 data rows using the dot-matrix font.
  function renderTableView(rows, scrollOffset, mode, angle) {
    buf.fill(0);

    // Status bar
    const statusLine = (mode || 'TABLE').padEnd(6) + (angle || 'DEG');
    drawText(statusLine, 0, 0);

    // Column header (abbreviated to fit 21 chars)
    drawText('  X        F(X)     ', 0, 9);

    // Divider line
    for (let x = 0; x < W; x++) setPixel(x, 16, 1);

    // Data rows — 5 visible at a time
    const vis = rows.slice(scrollOffset, scrollOffset + 5);
    for (let i = 0; i < vis.length; i++) {
      const r = vis[i];
      const xStr = String(r.x).slice(0, 9).padStart(9);
      const yStr = (r.y === undefined || r.y === null ? '---' : String(r.y))
        .slice(0, 10).padStart(10);
      drawText(xStr + ' ' + yStr, 0, 18 + i * 8);
    }

    // Scroll indicator (right edge, single pixel marker)
    if (rows.length > 5) {
      const maxOff = rows.length - 5;
      const barY = 18 + Math.round((scrollOffset / maxOff) * 38);
      setPixel(127, barY, 1);
      setPixel(127, barY + 1, 1);
    }

    _drawSoftkeyBar(_softkeys);
    flush();
  }

  // ── public: render Locate-command grid from a running program ─────────────
  // locateBuf: { rowStr: { colStr: text } }  (1-indexed, as from applyPrgmEvents)
  // Row 1..8 → pixels 8..57 (7px per row, tightly packed to fit 8 rows)
  // Col 1..21 → pixels 0..120 (6px per col, 5px char + 1px gap)
  function renderLocateGrid(locateBuf, mode, angle) {
    buf.fill(0);
    // Status bar
    const statusLine = (mode || 'PRGM').padEnd(6) + (angle || 'DEG');
    drawText(statusLine, 0, 0);
    // Located text
    for (const [rowKey, cols] of Object.entries(locateBuf)) {
      const r = parseInt(rowKey);
      if (r < 1 || r > 8) continue;
      const pixelY = 8 + (r - 1) * 7;
      for (const [colKey, text] of Object.entries(cols)) {
        const c = parseInt(colKey);
        if (c < 1 || c > 21) continue;
        const pixelX = (c - 1) * 6;
        drawText(String(text), pixelX, pixelY);
      }
    }
    _drawSoftkeyBar(_softkeys);
    flush();
  }

  // ── public: clear ─────────────────────────────────────────────────────────
  function clear() {
    buf.fill(0);
    flush();
  }

  // ── init ──────────────────────────────────────────────────────────────────
  function init(canvasEl) {
    canvas = canvasEl;
    canvas.width = PW;
    canvas.height = PH;
    ctx = canvas.getContext('2d');
    // Show COMP mode initial state on boot
    render({ mode: 'COMP', angle: 'DEG', shift: false, alpha: false,
             expression: '', result: '', error: '' });
  }

  return { init, render, clear, renderMenu, setSoftkeys,
           renderPixelMap, renderTableView, renderLocateGrid,
           drawText, drawRect, flush };
})();
