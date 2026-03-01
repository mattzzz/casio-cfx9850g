/**
 * Casio CFX-9850G — GRAPH and TABLE mode frontend
 *
 * GRAPH mode: sends functions + window to /api/graph/plot, renders inline SVG
 * TABLE mode: sends function + range to /api/table/generate, renders value table
 */

'use strict';

const Graph = (() => {

  // ── State ──────────────────────────────────────────────────────────────────
  let functions = ['', '', ''];
  let window_cfg = {
    xmin: -6.3, xmax: 6.3, xscl: 1,
    ymin: -3.1, ymax: 3.1, yscl: 1,
  };
  let angleMode = 'DEG';

  // ── Graph mode ─────────────────────────────────────────────────────────────

  async function plot(fns, win, angle) {
    if (fns) functions = fns;
    if (win) window_cfg = { ...window_cfg, ...win };
    if (angle) angleMode = angle;

    const resp = await fetch('/api/graph/plot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        functions,
        window: window_cfg,
        angle_mode: angleMode,
      }),
    });
    const data = await resp.json();
    return data.svg || '';
  }

  function renderSVG(svgStr) {
    const lcdEl = document.getElementById('lcd');
    if (!lcdEl) return;
    // Replace canvas with an SVG div overlay
    let svgContainer = document.getElementById('graph-svg-container');
    if (!svgContainer) {
      svgContainer = document.createElement('div');
      svgContainer.id = 'graph-svg-container';
      svgContainer.style.cssText =
        'position:absolute;top:0;left:0;width:100%;height:100%;z-index:2;';
      lcdEl.parentElement.style.position = 'relative';
      lcdEl.parentElement.appendChild(svgContainer);
    }
    svgContainer.innerHTML = svgStr;
    const svgEl = svgContainer.querySelector('svg');
    if (svgEl) {
      svgEl.setAttribute('width', '100%');
      svgEl.setAttribute('height', '100%');
      svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    }
    // Use visibility:hidden (not display:none) to keep the canvas in flow
    // so the parent #screen-bezel retains its dimensions
    lcdEl.style.visibility = 'hidden';
    svgContainer.style.display = 'block';
  }

  function hideGraph() {
    const lcdEl = document.getElementById('lcd');
    const svgContainer = document.getElementById('graph-svg-container');
    if (lcdEl) { lcdEl.style.display = 'block'; lcdEl.style.visibility = 'visible'; }
    if (svgContainer) svgContainer.style.display = 'none';
  }

  // ── Table mode ─────────────────────────────────────────────────────────────

  async function generateTable(fn, start, end, step, angle) {
    const resp = await fetch('/api/table/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        function: fn,
        start: parseFloat(start),
        end: parseFloat(end),
        step: parseFloat(step),
        angle_mode: angle || angleMode,
      }),
    });
    return resp.json();
  }

  function renderTable(data) {
    const lcdEl = document.getElementById('lcd');
    if (!lcdEl) return;

    let tableContainer = document.getElementById('table-container');
    if (!tableContainer) {
      tableContainer = document.createElement('div');
      tableContainer.id = 'table-container';
      tableContainer.style.cssText =
        'position:absolute;top:0;left:0;width:100%;height:100%;z-index:2;' +
        'background:#a8b84b;overflow-y:auto;font-family:monospace;font-size:11px;' +
        'color:#1c2314;padding:4px;box-sizing:border-box;';
      lcdEl.parentElement.style.position = 'relative';
      lcdEl.parentElement.appendChild(tableContainer);
    }

    if (data.error) {
      tableContainer.innerHTML =
        `<div style="color:#b84800;padding:4px">${data.error}</div>`;
    } else {
      const header = '<div style="display:flex;gap:16px;font-weight:bold;border-bottom:1px solid #1c2314;margin-bottom:2px">' +
        '<span style="width:60px">X</span><span>F(X)</span></div>';
      const rows = data.rows.map(r =>
        `<div style="display:flex;gap:16px"><span style="width:60px">${r.x}</span><span>${r.y}</span></div>`
      ).join('');
      tableContainer.innerHTML = header + rows;
    }

    lcdEl.style.visibility = 'hidden';
    tableContainer.style.display = 'block';

    // Also hide SVG container if visible
    const svgContainer = document.getElementById('graph-svg-container');
    if (svgContainer) svgContainer.style.display = 'none';
  }

  function hideTable() {
    const lcdEl = document.getElementById('lcd');
    const tableContainer = document.getElementById('table-container');
    if (lcdEl) { lcdEl.style.display = 'block'; lcdEl.style.visibility = 'visible'; }
    if (tableContainer) tableContainer.style.display = 'none';
  }

  return { plot, renderSVG, hideGraph, generateTable, renderTable, hideTable };
})();
