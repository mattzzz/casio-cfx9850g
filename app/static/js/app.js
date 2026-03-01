/**
 * Casio CFX-9850G — Entry point + WebSocket client
 *
 * State machine:
 *   appMode     : 'MENU' | 'COMP' | 'GRAPH' | 'TABLE' | <other>
 *   graphSub    : 'IDLE' | 'Y_INPUT' | 'WIN_INPUT' | 'DRAWN'
 *   menuVisible : true while MAIN MENU grid is showing
 */

'use strict';

(function () {
  const lcdEl = document.getElementById('lcd');
  LCD.init(lcdEl);

  // ── Application state ────────────────────────────────────────────────────
  // Start in COMP/RUN mode — the real CFX-9850G powers on in its last mode.
  // MENU is only shown when the user explicitly presses the MENU key.
  let appMode     = 'COMP';
  let menuVisible = false;
  let angleMode   = 'DEG';

  // GRAPH sub-state
  let graphSub       = 'IDLE';
  let graphYBuffer   = '';           // expression being typed for Y1
  let graphFunctions = ['', '', '']; // Y1, Y2, Y3
  let graphWindow    = {
    xmin: -6.3, xmax: 6.3, xscl: 1,
    ymin: -3.1, ymax: 3.1, yscl: 1,
  };

  // Local modifier state for GRAPH Y= input (not handled by backend)
  let graphAlpha = false;
  let graphShift = false;

  // TABLE sub-state (simple: use last COMP expression or manual entry)
  let tableFn    = 'X**2';
  let tableStart = 1, tableEnd = 10, tableStep = 1;

  // ── WebSocket ────────────────────────────────────────────────────────────
  const wsUrl = `ws://${location.host}/ws/calculator`;
  let ws;
  let reconnectTimer = null;

  function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    };
    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.type === 'display') {
        angleMode = msg.angle || 'DEG';
        // Only render to LCD when COMP mode is active and the MENU is not showing.
        // Guarding here prevents WS responses from overwriting the MENU screen.
        if (appMode === 'COMP' && !menuVisible) {
          msg.softkeys = Modes.getSoftkeys('COMP');
          LCD.render(msg);
        }
      }
    };
    ws.onerror = () => {};
    ws.onclose = () => { reconnectTimer = setTimeout(connect, 2000); };
  }

  function sendKey(key) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'key', key }));
    }
  }

  // ── Mode map: number key → mode name ─────────────────────────────────────
  const MENU_MODE_MAP = {
    '1': 'COMP',
    '2': 'STAT',
    '3': 'GRAPH',
    '4': 'DYNA',
    '5': 'TABLE',
    '6': 'RECR',
    '7': 'EQUA',
    '8': 'PRGM',
    '9': 'MAT',
  };

  // ── Key → expression text for graph Y= entry ─────────────────────────────
  const GRAPH_KEY_TEXT = {
    '0':'0','1':'1','2':'2','3':'3','4':'4',
    '5':'5','6':'6','7':'7','8':'8','9':'9',
    'DOT':'.', 'PLUS':'+', 'MINUS':'-',
    'MUL':'*', 'DIV':'/',
    'LPAREN':'(', 'RPAREN':')',
    'XTHETA':'X',
    'SIN':'sin(', 'COS':'cos(', 'TAN':'tan(',
    'LOG':'log(', 'LN':'ln(',
    'SQR':'**2', 'POW':'**',
    'NEG':'-', 'EXP':'E',
    'PI':'pi',
  };

  // ALPHA+key → variable letter (mirrors comp.py _ALPHA_KEYS)
  const GRAPH_ALPHA_TEXT = {
    'XTHETA':'A', 'LOG':'B', 'LN':'C', 'SIN':'D', 'COS':'E', 'TAN':'F',
    'FRAC':'G', 'FD':'H', 'LPAREN':'I', 'RPAREN':'J', 'COMMA':'K', 'ARROW':'L',
    '7':'M', '8':'N', '9':'O', '4':'P', '5':'Q', '6':'R',
    'MUL':'S', 'DIV':'T', '1':'U', '2':'V', '3':'W',
    'PLUS':'X', 'MINUS':'Y', '0':'Z',
    'EXP':'pi', 'NEG':'Ans',
  };

  // SHIFT+key → alternate function text for graph Y= entry
  const GRAPH_SHIFT_TEXT = {
    'SIN':'asin(', 'COS':'acos(', 'TAN':'atan(',
    'LOG':'10**(', 'LN':'e**(',
    'SQR':'sqrt(',
  };

  // ── Mode switcher ─────────────────────────────────────────────────────────
  function switchToMode(mode) {
    appMode = mode;
    menuVisible = false;
    Modes.setMode(mode);
    LCD.setSoftkeys(Modes.getSoftkeys(mode));

    Graph.hideGraph();
    Graph.hideTable();

    graphAlpha = false;
    graphShift = false;

    if (mode === 'COMP') {
      graphSub = 'IDLE';
      sendKey('AC');   // refresh COMP display via backend

    } else if (mode === 'GRAPH') {
      // If no function stored yet, drop straight into Y= entry
      if (graphFunctions.some(f => f)) {
        graphSub = 'IDLE';
        showGraphIdle();
      } else {
        graphYBuffer = '';
        showYInput();
      }

    } else if (mode === 'TABLE') {
      graphSub = 'IDLE';
      showTableIdle();

    } else {
      // Unimplemented mode — show placeholder
      LCD.render({
        type: 'display',
        mode, angle: angleMode,
        shift: false, alpha: false,
        expression: mode + ' MODE',
        result: 'Coming soon',
        error: '',
      });
    }
  }

  // ── MENU screen ───────────────────────────────────────────────────────────
  function showMenu() {
    appMode = 'MENU';
    menuVisible = true;
    Modes.setMode('MENU');
    Graph.hideGraph();
    Graph.hideTable();
    LCD.setSoftkeys(Modes.getSoftkeys('MENU'));
    LCD.renderMenu();
  }

  // ── GRAPH mode helpers ────────────────────────────────────────────────────
  function showGraphIdle() {
    LCD.render({
      type: 'display',
      mode: 'GRAPH', angle: angleMode,
      shift: false, alpha: false,
      expression: 'Y1=' + (graphFunctions[0] || '?'),
      result: graphFunctions[1] ? 'Y2=' + graphFunctions[1] : '',
      error: '',
      softkeys: Modes.getSoftkeys('GRAPH'),
    });
  }

  function showYInput() {
    graphSub = 'Y_INPUT';
    // Show a blinking cursor-like underscore at the end
    LCD.render({
      type: 'display',
      mode: 'GRAPH', angle: angleMode,
      shift: graphShift, alpha: graphAlpha,
      expression: 'Y1=' + graphYBuffer + '_',
      result: graphShift ? 'SHIFT' : (graphAlpha ? 'ALPHA' : ''),
      error: '',
      softkeys: Modes.getSoftkeys('GRAPH'),
    });
  }

  async function drawGraph() {
    graphSub = 'DRAWN';
    try {
      const svg = await Graph.plot(graphFunctions, graphWindow, angleMode);
      Graph.hideTable();
      Graph.renderSVG(svg);
    } catch (e) {
      LCD.render({
        type: 'display',
        mode: 'GRAPH', angle: angleMode,
        shift: false, alpha: false,
        expression: 'Graph ERROR',
        result: '', error: '',
        softkeys: Modes.getSoftkeys('GRAPH'),
      });
    }
  }

  // ── TABLE mode helpers ────────────────────────────────────────────────────
  function showTableIdle() {
    LCD.render({
      type: 'display',
      mode: 'TABLE', angle: angleMode,
      shift: false, alpha: false,
      expression: 'F(X)=' + tableFn,
      result: 'Press F3:TABL',
      error: '',
      softkeys: Modes.getSoftkeys('TABLE'),
    });
  }

  async function generateAndShowTable() {
    try {
      const data = await Graph.generateTable(tableFn, tableStart, tableEnd, tableStep, angleMode);
      Graph.hideGraph();
      Graph.renderTable(data);
    } catch (e) {
      LCD.render({
        type: 'display',
        mode: 'TABLE', angle: angleMode,
        shift: false, alpha: false,
        expression: 'Table ERROR',
        result: '', error: '',
        softkeys: Modes.getSoftkeys('TABLE'),
      });
    }
  }

  // ── Key handler ───────────────────────────────────────────────────────────
  function handleKey(key) {

    // ── MENU key: always show MAIN MENU (except during text input) ─────────
    if (key === 'MENU') {
      showMenu();
      return;
    }

    // ── MAIN MENU screen: number keys select modes ──────────────────────────
    if (menuVisible) {
      const targetMode = MENU_MODE_MAP[key];
      if (targetMode) {
        switchToMode(targetMode);
      }
      // Ignore other keys while menu is showing
      return;
    }

    // ── Dispatch to active mode (each mode handles EXIT itself) ─────────────
    if (appMode === 'COMP') {
      handleCompKey(key);
    } else if (appMode === 'GRAPH') {
      handleGraphKey(key);
    } else if (appMode === 'TABLE') {
      handleTableKey(key);
    } else {
      // Unimplemented modes: EXIT returns to menu
      if (key === 'EXIT') showMenu();
    }
  }

  // ── COMP mode ─────────────────────────────────────────────────────────────
  function handleCompKey(key) {
    if (key === 'EXIT') { showMenu(); return; }
    // All other COMP keys go to backend; replay buffer handled there
    sendKey(key);
  }

  // ── GRAPH mode ────────────────────────────────────────────────────────────
  function handleGraphKey(key) {

    if (graphSub === 'Y_INPUT') {
      // ── Y= expression entry ──

      // Handle modifiers locally — backend is not involved in GRAPH Y= input
      if (key === 'ALPHA') {
        graphAlpha = !graphAlpha;
        graphShift = false;
        showYInput();
        return;
      }
      if (key === 'SHIFT') {
        graphShift = !graphShift;
        graphAlpha = false;
        showYInput();
        return;
      }

      if (key === 'EXE' || key === 'F6') {
        graphAlpha = false; graphShift = false;
        graphFunctions[0] = graphYBuffer;
        graphYBuffer = '';
        drawGraph();
        return;
      }
      if (key === 'AC') {
        graphAlpha = false; graphShift = false;
        graphYBuffer = '';
        showYInput();
        return;
      }
      if (key === 'DEL') {
        graphAlpha = false; graphShift = false;
        graphYBuffer = graphYBuffer.slice(0, -1);
        showYInput();
        return;
      }
      if (key === 'EXIT') {
        // EXIT from Y= entry → back to GRAPH idle (not all the way to MENU)
        graphAlpha = false; graphShift = false;
        graphSub = 'IDLE';
        showGraphIdle();
        return;
      }

      // Look up the character to insert, applying any active modifier
      let ch;
      if (graphAlpha) {
        ch = GRAPH_ALPHA_TEXT[key];
        graphAlpha = false;
      } else if (graphShift) {
        ch = GRAPH_SHIFT_TEXT[key] !== undefined ? GRAPH_SHIFT_TEXT[key] : GRAPH_KEY_TEXT[key];
        graphShift = false;
      } else {
        ch = GRAPH_KEY_TEXT[key];
      }
      if (ch !== undefined) {
        graphYBuffer += ch;
        showYInput();
      }
      return;
    }

    // ── IDLE / DRAWN state ──
    if (key === 'EXIT') { showMenu(); return; }

    if (key === 'F1') {          // Y=  — open function entry
      graphYBuffer = graphFunctions[0] || '';
      showYInput();
      return;
    }

    if (key === 'F2') {          // WIN — V-Window (basic: show current window)
      LCD.render({
        type: 'display',
        mode: 'GRAPH', angle: angleMode,
        shift: false, alpha: false,
        expression: `Xmin:${graphWindow.xmin} Xmax:${graphWindow.xmax}`,
        result:     `Ymin:${graphWindow.ymin} Ymax:${graphWindow.ymax}`,
        error: '',
        softkeys: Modes.getSoftkeys('GRAPH'),
      });
      graphSub = 'IDLE';
      Graph.hideGraph();
      return;
    }

    if (key === 'F3') {          // ZOOM — zoom in
      graphWindow.xmin *= 0.5;
      graphWindow.xmax *= 0.5;
      graphWindow.ymin *= 0.5;
      graphWindow.ymax *= 0.5;
      if (graphSub === 'DRAWN') drawGraph();
      return;
    }

    if (key === 'F4') {          // TRCE — placeholder
      LCD.render({
        type: 'display',
        mode: 'GRAPH', angle: angleMode,
        shift: false, alpha: false,
        expression: 'TRACE: use arrows',
        result: '', error: '',
        softkeys: Modes.getSoftkeys('GRAPH'),
      });
      return;
    }

    if (key === 'F6' || key === 'EXE') {   // DRAW — draw graph
      if (graphFunctions.some(f => f)) {
        drawGraph();
      } else {
        // No function set yet — jump straight to Y= entry
        graphYBuffer = '';
        showYInput();
      }
      return;
    }

    if (key === 'F5') {          // (unassigned in this softkey set)
      return;
    }

    if (key === 'AC') {
      graphSub = 'IDLE';
      graphFunctions = ['', '', ''];
      Graph.hideGraph();
      Graph.hideTable();
      graphYBuffer = '';
      showYInput();
      return;
    }

    // Any character key in IDLE/DRAWN state auto-opens Y= input
    const ch = GRAPH_KEY_TEXT[key];
    if (ch !== undefined) {
      graphYBuffer = graphFunctions[0] || '';
      graphYBuffer += ch;
      showYInput();
    }
  }

  // ── TABLE mode ────────────────────────────────────────────────────────────
  function handleTableKey(key) {
    if (key === 'EXIT') { showMenu(); return; }
    if (key === 'F3') {          // TABL — generate table
      generateAndShowTable();
      return;
    }
    if (key === 'F1') {          // FORM — edit function (basic prompt)
      LCD.render({
        type: 'display',
        mode: 'TABLE', angle: angleMode,
        shift: false, alpha: false,
        expression: 'F(X)=' + tableFn,
        result: 'EXE to confirm',
        error: '',
        softkeys: Modes.getSoftkeys('TABLE'),
      });
      Graph.hideTable();
      return;
    }
    if (key === 'F4') {          // G-PLT — graph the table function
      switchToMode('GRAPH');
      graphFunctions[0] = tableFn;
      drawGraph();
      return;
    }
    if (key === 'AC') {
      Graph.hideTable();
      showTableIdle();
    }
  }

  // ── Startup ───────────────────────────────────────────────────────────────
  Keyboard.init(handleKey);
  connect();

  // Show MAIN MENU on load (LCD.init already rendered it; this ensures WS is connected)
  // After connection the menu stays until user selects a mode.
})();
