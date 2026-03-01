/**
 * Casio CFX-9850G — GRAPH and TABLE mode frontend
 *
 * All output goes through the dot-matrix LCD canvas (LCD object).
 * No raw HTML/SVG overlays — everything is rendered as LCD pixels.
 *
 * GRAPH: fetches 128×64 pixel map from /api/graph/pixels → LCD.renderPixelMap()
 * TABLE: fetches rows from /api/table/generate → LCD.renderTableView()
 */

'use strict';

const Graph = (() => {

  // ── State ──────────────────────────────────────────────────────────────────
  let _functions  = ['', '', ''];
  let _window     = { xmin: -6.3, xmax: 6.3, xscl: 1, ymin: -3.1, ymax: 3.1, yscl: 1 };
  let _angleMode  = 'DEG';

  // ── Graph mode ─────────────────────────────────────────────────────────────

  /** Fetch and return 128×64 pixel array from the server. */
  async function plotPixels(fns, win, angle) {
    if (fns)   _functions  = fns;
    if (win)   _window     = { ..._window, ...win };
    if (angle) _angleMode  = angle;

    const resp = await fetch('/api/graph/pixels', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        functions:  _functions,
        window:     _window,
        angle_mode: _angleMode,
      }),
    });
    const data = await resp.json();
    return data.pixels || [];
  }

  /** Render a pixel array (8192 ints 0/1) onto the LCD canvas. */
  function renderPixels(pixelArr) {
    LCD.renderPixelMap(pixelArr);
  }

  // Keep legacy `plot` + `renderSVG` names so callers don't break
  // (they now do the same thing as the pixel path)
  async function plot(fns, win, angle) {
    return plotPixels(fns, win, angle);
  }
  function renderSVG(pixels) {
    // pixels is now actually a pixel array (from plotPixels)
    LCD.renderPixelMap(pixels);
  }

  // No-op shims — no HTML overlay to hide any more
  function hideGraph()  {}
  function hideTable()  {}

  // ── Table mode ─────────────────────────────────────────────────────────────

  /** Fetch table data from the server. Returns {rows, error}. */
  async function generateTable(fn, start, end, step, angle) {
    const resp = await fetch('/api/table/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        function:   fn,
        start:      parseFloat(start),
        end:        parseFloat(end),
        step:       parseFloat(step),
        angle_mode: angle || _angleMode,
      }),
    });
    return resp.json();
  }

  /** Render table data onto the LCD canvas using the dot-matrix text renderer. */
  function renderTable(data, scrollOffset, mode, angle) {
    if (data.error) {
      LCD.render({
        type: 'display', mode: mode || 'TABLE', angle: angle || _angleMode,
        shift: false, alpha: false,
        expression: 'Table ERROR', result: data.error, error: '',
      });
      return;
    }
    LCD.renderTableView(data.rows || [], scrollOffset || 0, mode, angle);
  }

  return {
    // Graph
    plotPixels, renderPixels,
    plot, renderSVG,          // legacy shims
    hideGraph, hideTable,     // no-op shims
    // Table
    generateTable, renderTable,
  };
})();
