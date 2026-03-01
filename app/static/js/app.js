/**
 * Casio CFX-9850G — Entry point + WebSocket client
 *
 * All display output goes through the dot-matrix LCD canvas.
 * No raw HTML/SVG overlays — everything uses LCD.render(),
 * LCD.renderPixelMap(), or LCD.renderTableView().
 *
 * appMode: 'MENU' | 'COMP' | 'GRAPH' | 'TABLE' |
 *          'STAT' | 'EQUA' | 'MAT' | 'BASE' | 'DYNA' | 'RECR' | 'PRGM'
 */

'use strict';

(function () {
  const lcdEl = document.getElementById('lcd');
  LCD.init(lcdEl);

  // ── Application state ────────────────────────────────────────────────────
  let appMode     = 'COMP';
  let menuVisible = false;
  let angleMode   = 'DEG';

  // ── GRAPH sub-state ──────────────────────────────────────────────────────
  let graphSub       = 'IDLE';
  let graphYBuffer   = '';
  let graphFunctions = ['', '', ''];
  let graphWindow    = { xmin: -6.3, xmax: 6.3, xscl: 1, ymin: -3.1, ymax: 3.1, yscl: 1 };
  let graphAlpha = false, graphShift = false;

  // ── TABLE sub-state ──────────────────────────────────────────────────────
  let tableFn    = 'X**2';
  let tableStart = 1, tableEnd = 10, tableStep = 1;
  let tableData  = null;   // last fetched {rows, error}
  let tableScroll = 0;

  // ── STAT sub-state ───────────────────────────────────────────────────────
  let statPhase   = '1VAR';   // '1VAR' | '2VAR' | 'REG'
  let statInput   = '';
  let statResult  = null;

  // ── EQUA sub-state ───────────────────────────────────────────────────────
  let equaPhase   = 'POLY';   // 'POLY' | 'SIML'
  let equaInput   = '';
  let equaResult  = null;

  // ── MAT sub-state ────────────────────────────────────────────────────────
  let matPhase    = 'SELECT'; // 'SELECT' | 'DATA' | 'RESULT'
  let matName     = 'A';
  let matInput    = '';
  let matResult   = null;

  // ── BASE-N sub-state ─────────────────────────────────────────────────────
  let baseBase    = 'DEC';    // 'DEC' | 'HEX' | 'BIN' | 'OCT'
  let baseInput   = '';
  let baseResult  = null;

  // ── WebSocket ────────────────────────────────────────────────────────────
  const wsUrl = `ws://${location.host}/ws/calculator`;
  let ws, reconnectTimer = null;

  function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => { if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; } };
    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.type === 'display' && appMode === 'COMP' && !menuVisible) {
        angleMode = msg.angle || 'DEG';
        msg.softkeys = Modes.getSoftkeys('COMP');
        LCD.render(msg);
      }
    };
    ws.onerror = () => {};
    ws.onclose = () => { reconnectTimer = setTimeout(connect, 2000); };
  }

  function sendKey(key) {
    if (ws && ws.readyState === WebSocket.OPEN)
      ws.send(JSON.stringify({ type: 'key', key }));
  }

  // ── Menu → mode map ──────────────────────────────────────────────────────
  const MENU_MODE_MAP = {
    '1': 'COMP', '2': 'STAT', '3': 'GRAPH',
    '4': 'DYNA', '5': 'TABLE', '6': 'RECR',
    '7': 'EQUA', '8': 'PRGM', '9': 'MAT',
  };

  // ── GRAPH key→text maps ──────────────────────────────────────────────────
  const GRAPH_KEY_TEXT = {
    '0':'0','1':'1','2':'2','3':'3','4':'4',
    '5':'5','6':'6','7':'7','8':'8','9':'9',
    'DOT':'.','PLUS':'+','MINUS':'-','MUL':'*','DIV':'/',
    'LPAREN':'(','RPAREN':')','XTHETA':'X',
    'SIN':'sin(','COS':'cos(','TAN':'tan(',
    'LOG':'log(','LN':'ln(','SQR':'**2','POW':'**',
    'NEG':'-','EXP':'E','PI':'pi',
  };
  const GRAPH_ALPHA_TEXT = {
    'XTHETA':'A','LOG':'B','LN':'C','SIN':'D','COS':'E','TAN':'F',
    'FRAC':'G','FD':'H','LPAREN':'I','RPAREN':'J','COMMA':'K','ARROW':'L',
    '7':'M','8':'N','9':'O','4':'P','5':'Q','6':'R',
    'MUL':'S','DIV':'T','1':'U','2':'V','3':'W',
    'PLUS':'X','MINUS':'Y','0':'Z','EXP':'pi','NEG':'Ans',
  };
  const GRAPH_SHIFT_TEXT = {
    'SIN':'asin(','COS':'acos(','TAN':'atan(',
    'LOG':'10**(','LN':'e**(','SQR':'sqrt(',
  };

  // ── Generic text-input key → character map (used by STAT/EQUA/MAT/BASE) ─
  const TEXT_KEY = {
    '0':'0','1':'1','2':'2','3':'3','4':'4',
    '5':'5','6':'6','7':'7','8':'8','9':'9',
    'DOT':'.','MINUS':'-','COMMA':',',
    'A':'A','B':'B','C':'C','D':'D','E':'E','F':'F', // for HEX
  };

  // ── Helper: pad a line to exactly 21 chars for multi-line expression ──────
  function pad21(s) { return s.slice(0, 21).padEnd(21); }

  // ── Mode switcher ─────────────────────────────────────────────────────────
  function switchToMode(mode) {
    appMode = mode;
    menuVisible = false;
    Modes.setMode(mode);
    LCD.setSoftkeys(Modes.getSoftkeys(mode));

    graphAlpha = false;
    graphShift = false;

    if (mode === 'COMP') {
      graphSub = 'IDLE';
      sendKey('AC');

    } else if (mode === 'GRAPH') {
      if (graphFunctions.some(f => f)) { graphSub = 'IDLE'; showGraphIdle(); }
      else { graphYBuffer = ''; showYInput(); }

    } else if (mode === 'TABLE') {
      graphSub = 'IDLE';
      tableScroll = 0;
      tableData = null;
      showTableIdle();

    } else if (mode === 'STAT') {
      statPhase = '1VAR'; statInput = ''; statResult = null;
      showStat();

    } else if (mode === 'EQUA') {
      equaPhase = 'POLY'; equaInput = ''; equaResult = null;
      showEqua();

    } else if (mode === 'MAT') {
      matPhase = 'SELECT'; matInput = ''; matResult = null;
      showMat();

    } else if (mode === 'BASE') {
      baseBase = 'DEC'; baseInput = ''; baseResult = null;
      showBase();

    } else {
      // DYNA, RECR, PRGM — not yet implemented
      LCD.render({
        type: 'display', mode, angle: angleMode, shift: false, alpha: false,
        expression: mode + ' MODE', result: 'Coming soon', error: '',
      });
    }
  }

  // ── MENU ──────────────────────────────────────────────────────────────────
  function showMenu() {
    appMode = 'MENU';
    menuVisible = true;
    Modes.setMode('MENU');
    LCD.setSoftkeys(Modes.getSoftkeys('MENU'));
    LCD.renderMenu();
  }

  // ── GRAPH mode ────────────────────────────────────────────────────────────
  function showGraphIdle() {
    LCD.render({
      type: 'display', mode: 'GRAPH', angle: angleMode, shift: false, alpha: false,
      expression: 'Y1=' + (graphFunctions[0] || '?'),
      result: graphFunctions[1] ? 'Y2=' + graphFunctions[1] : '',
      error: '', softkeys: Modes.getSoftkeys('GRAPH'),
    });
  }

  function showYInput() {
    graphSub = 'Y_INPUT';
    LCD.render({
      type: 'display', mode: 'GRAPH', angle: angleMode,
      shift: graphShift, alpha: graphAlpha,
      expression: 'Y1=' + graphYBuffer + '_',
      result: graphShift ? 'SHIFT' : (graphAlpha ? 'ALPHA' : ''),
      error: '', softkeys: Modes.getSoftkeys('GRAPH'),
    });
  }

  async function drawGraph() {
    graphSub = 'DRAWN';
    LCD.setSoftkeys(Modes.getSoftkeys('GRAPH'));
    try {
      const pixels = await Graph.plotPixels(graphFunctions, graphWindow, angleMode);
      Graph.renderPixels(pixels);
    } catch {
      LCD.render({
        type: 'display', mode: 'GRAPH', angle: angleMode,
        shift: false, alpha: false,
        expression: 'Graph ERROR', result: '', error: '',
        softkeys: Modes.getSoftkeys('GRAPH'),
      });
    }
  }

  // ── TABLE mode ────────────────────────────────────────────────────────────
  function showTableIdle() {
    LCD.render({
      type: 'display', mode: 'TABLE', angle: angleMode,
      shift: false, alpha: false,
      expression: 'F(X)=' + tableFn,
      result: 'F3:TABL to compute',
      error: '', softkeys: Modes.getSoftkeys('TABLE'),
    });
  }

  async function generateAndShowTable() {
    try {
      tableData = await Graph.generateTable(tableFn, tableStart, tableEnd, tableStep, angleMode);
      tableScroll = 0;
      Graph.renderTable(tableData, tableScroll, 'TABLE', angleMode);
    } catch {
      LCD.render({
        type: 'display', mode: 'TABLE', angle: angleMode,
        shift: false, alpha: false,
        expression: 'Table ERROR', result: '', error: '',
        softkeys: Modes.getSoftkeys('TABLE'),
      });
    }
  }

  // ── STAT mode ─────────────────────────────────────────────────────────────
  function showStat() {
    let expr, res;
    if (statResult && !('error' in statResult)) {
      if (statPhase === '1VAR') {
        expr = pad21('n=' + statResult.n + ' x=' + statResult.mean_x) +
               pad21('Sx=' + statResult.sum_x + ' Sx2=' + statResult.sum_x2) +
               pad21('sx=' + statResult.sigma_x + ' Sx=' + statResult.s_x) +
               pad21('min=' + statResult.min_x + ' max=' + statResult.max_x);
        res  = 'med=' + statResult.median;
      } else if (statPhase === '2VAR') {
        expr = pad21('n=' + statResult.n + ' x=' + statResult.mean_x + ' y=' + statResult.mean_y) +
               pad21('Sxy=' + statResult.sum_xy) +
               pad21('sx=' + statResult.sigma_x + ' sy=' + statResult.sigma_y) +
               pad21('Sxy=' + statResult.sum_xy);
        res  = 'Sx=' + statResult.s_x + ' Sy=' + statResult.s_y;
      } else {
        expr = pad21('y=a+bx (LINEAR)') +
               pad21('a=' + statResult.a) +
               pad21('b=' + statResult.b) +
               pad21('r=' + statResult.r);
        res  = 'r2=' + statResult.r2;
      }
    } else if (statResult && statResult.error) {
      expr = statResult.error;
      res  = '';
    } else {
      const hint = statPhase === '1VAR' ? 'X values: 1,2,3,...' :
                   statPhase === '2VAR' ? 'X,Y pairs: 1,4,2,5' :
                                         'X,Y pairs then EXE';
      expr = pad21('STAT ' + statPhase) + pad21(hint) + pad21('Input:') + pad21(statInput + '_');
      res  = '';
    }
    LCD.render({
      type: 'display', mode: 'STAT', angle: angleMode,
      shift: false, alpha: false,
      expression: expr, result: res, error: '',
      softkeys: Modes.getSoftkeys('STAT'),
    });
  }

  async function handleStatKey(key) {
    if (key === 'EXIT') { showMenu(); return; }
    if (key === 'F1') { statPhase = '1VAR'; statInput = ''; statResult = null; showStat(); return; }
    if (key === 'F2') { statPhase = '2VAR'; statInput = ''; statResult = null; showStat(); return; }
    if (key === 'F3') { statPhase = 'REG';  statInput = ''; statResult = null; showStat(); return; }
    if (key === 'AC')  { statInput = ''; statResult = null; showStat(); return; }
    if (key === 'DEL') { statInput = statInput.slice(0, -1); statResult = null; showStat(); return; }

    // Character input
    const ch = key === 'DOT' ? '.' : key === 'COMMA' ? ',' : key === 'MINUS' ? '-' :
               /^[0-9]$/.test(key) ? key : null;
    if (ch !== null) { statInput += ch; statResult = null; showStat(); return; }

    if (key === 'EXE') {
      const nums = statInput.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
      if (nums.length === 0) return;
      try {
        let resp, data;
        if (statPhase === '1VAR') {
          resp = await fetch('/api/stat/one_var', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({x: nums}),
          });
        } else {
          const xs = [], ys = [];
          for (let i = 0; i + 1 < nums.length; i += 2) { xs.push(nums[i]); ys.push(nums[i+1]); }
          if (statPhase === '2VAR') {
            resp = await fetch('/api/stat/two_var', {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({x: xs, y: ys}),
            });
          } else {
            resp = await fetch('/api/stat/regression', {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({x: xs, y: ys, type: 'linear'}),
            });
          }
        }
        statResult = await resp.json();
        showStat();
      } catch { statResult = {error: 'Network ERROR'}; showStat(); }
    }
  }

  // ── EQUA mode ─────────────────────────────────────────────────────────────
  function showEqua() {
    let expr, res;
    if (equaResult && !('error' in equaResult)) {
      if (equaPhase === 'POLY') {
        const roots = equaResult.roots || [];
        expr = pad21('POLY deg=' + equaResult.degree + ' roots:') +
               roots.slice(0, 3).map((r, i) => pad21('x' + (i+1) + '=' + r)).join('');
        res  = roots.length > 3 ? 'x4=' + roots[3] : '';
      } else {
        const sol = equaResult.solution || [];
        expr = pad21('SIML solution:') +
               sol.map((v, i) => pad21('x' + (i+1) + '=' + v)).slice(0, 3).join('');
        res  = sol.length > 3 ? 'x4=' + sol[3] : '';
      }
    } else if (equaResult && equaResult.error) {
      expr = pad21('EQUA ' + equaPhase) + pad21(equaResult.error);
      res  = '';
    } else {
      const hint = equaPhase === 'POLY'
        ? '1,-5,6  (hi→lo)'
        : '1,1,5;2,-1,1';
      expr = pad21('EQUA ' + equaPhase) +
             pad21(equaPhase === 'POLY' ? 'Coeff hi→lo:' : 'Rows (;=newrow):') +
             pad21(hint) +
             pad21(equaInput + '_');
      res  = '';
    }
    LCD.render({
      type: 'display', mode: 'EQUA', angle: angleMode,
      shift: false, alpha: false,
      expression: expr, result: res, error: '',
      softkeys: Modes.getSoftkeys('EQUA'),
    });
  }

  async function handleEquaKey(key) {
    if (key === 'EXIT') { showMenu(); return; }
    if (key === 'F1') { equaPhase = 'POLY'; equaInput = ''; equaResult = null; showEqua(); return; }
    if (key === 'F2') { equaPhase = 'SIML'; equaInput = ''; equaResult = null; showEqua(); return; }
    if (key === 'AC')  { equaInput = ''; equaResult = null; showEqua(); return; }
    if (key === 'DEL') { equaInput = equaInput.slice(0, -1); equaResult = null; showEqua(); return; }

    const ch = key === 'DOT' ? '.' : key === 'COMMA' ? ',' : key === 'MINUS' ? '-' :
               key === 'SEMICOLON' || key === 'F3' ? ';' :
               /^[0-9]$/.test(key) ? key : null;
    if (ch !== null) { equaInput += ch; equaResult = null; showEqua(); return; }

    if (key === 'EXE') {
      try {
        let resp;
        if (equaPhase === 'POLY') {
          const coeffs = equaInput.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n));
          resp = await fetch('/api/equa/polynomial', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({coefficients: coeffs}),
          });
        } else {
          // Parse "a,b,c;d,e,f" → matrix rows + last col is constants
          const rows = equaInput.split(';').map(r => r.split(',').map(n => parseFloat(n.trim())));
          const n = rows.length;
          const matrix = rows.map(r => r.slice(0, n));
          const constants = rows.map(r => r[n] ?? 0);
          resp = await fetch('/api/equa/simultaneous', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({matrix, constants}),
          });
        }
        equaResult = await resp.json();
        showEqua();
      } catch { equaResult = {error: 'Network ERROR'}; showEqua(); }
    }
  }

  // ── MAT mode ──────────────────────────────────────────────────────────────
  // matInput format:
  //   SELECT phase: user presses F1-F6 to pick A-F
  //   DATA phase:   user types "2,2;1,2,3,4" → 2×2 matrix [[1,2],[3,4]]
  //                 (dims before ; , elements after as flat list)
  //   RESULT phase: show result, F1=DET, F2=INV, F3=RREF, F4=TRN

  const MAT_NAMES = ['A','B','C','D','E','F'];

  function showMat() {
    let expr, res;
    if (matPhase === 'SELECT') {
      expr = pad21('MAT: select A-F') + pad21('F1=A F2=B F3=C') + pad21('F4=D F5=E F6=F');
      res  = '';
    } else if (matPhase === 'DATA') {
      expr = pad21('Mat ' + matName + ': enter data') +
             pad21('rows,cols;e1,e2,...') +
             pad21(matInput + '_');
      res  = matResult && matResult.error ? matResult.error : '';
    } else {
      // RESULT
      if (matResult && !matResult.error && matResult.matrix) {
        const rows = matResult.matrix;
        expr = pad21('Mat ' + matName + ' result:') +
               rows.slice(0, 3).map(r => pad21('[' + r.join(' ') + ']')).join('');
        res  = rows.length > 3 ? '[' + rows[3].join(' ') + ']' : 'F1=DET F2=INV F3=RREF';
      } else if (matResult && matResult.result !== undefined) {
        expr = pad21('Mat ' + matName + ':') + pad21('Result: ' + matResult.result);
        res  = 'F1=DET F2=INV F3=RREF';
      } else if (matResult && matResult.error) {
        expr = pad21('Mat ' + matName + ' ERROR:') + pad21(matResult.error);
        res  = '';
      } else {
        expr = pad21('Mat ' + matName + ' stored.') + pad21('F1=DET F2=INV') + pad21('F3=RREF F4=TRN');
        res  = '';
      }
    }
    LCD.render({
      type: 'display', mode: 'MAT', angle: angleMode,
      shift: false, alpha: false,
      expression: expr, result: res, error: '',
      softkeys: Modes.getSoftkeys('MAT'),
    });
  }

  // Shared matrix store per session (for operations)
  let _matrixStore = {};

  async function handleMatKey(key) {
    if (key === 'EXIT') {
      if (matPhase !== 'SELECT') { matPhase = 'SELECT'; matInput = ''; matResult = null; showMat(); }
      else showMenu();
      return;
    }

    if (matPhase === 'SELECT') {
      const fkeyIdx = ['F1','F2','F3','F4','F5','F6'].indexOf(key);
      if (fkeyIdx >= 0) {
        matName = MAT_NAMES[fkeyIdx];
        matPhase = 'DATA'; matInput = ''; matResult = null;
        showMat();
      }
      return;
    }

    if (matPhase === 'DATA') {
      if (key === 'AC') { matInput = ''; matResult = null; showMat(); return; }
      if (key === 'DEL') { matInput = matInput.slice(0,-1); matResult = null; showMat(); return; }
      const ch = key === 'DOT' ? '.' : key === 'COMMA' ? ',' : key === 'MINUS' ? '-' :
                 key === 'F3' ? ';' :   // F3 acts as semicolon separator
                 /^[0-9]$/.test(key) ? key : null;
      if (ch !== null) { matInput += ch; matResult = null; showMat(); return; }

      if (key === 'EXE') {
        // Parse input: "rows,cols;e1,e2,..." e.g. "2,2;1,2,3,4"
        const parts = matInput.split(';');
        if (parts.length < 2) { matResult = {error: 'Use rows,cols;data'}; showMat(); return; }
        const dims = parts[0].split(',').map(n => parseInt(n));
        const elems = parts[1].split(',').map(n => parseFloat(n.trim()));
        const [nrows, ncols] = dims;
        if (isNaN(nrows) || isNaN(ncols) || elems.length !== nrows * ncols) {
          matResult = {error: 'Dimension ERROR'}; showMat(); return;
        }
        const rows = [];
        for (let r = 0; r < nrows; r++) rows.push(elems.slice(r * ncols, (r+1)*ncols));
        _matrixStore[matName] = rows;
        matPhase = 'RESULT'; matResult = null; showMat(); return;
      }
      return;
    }

    if (matPhase === 'RESULT') {
      const ops = {F1:'det', F2:'inv', F3:'rref', F4:'transpose'};
      const op = ops[key];
      if (op) {
        try {
          const resp = await fetch('/api/matrix/calculate', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({op, a: matName, matrices: {[matName]: _matrixStore[matName]}}),
          });
          matResult = await resp.json();
          showMat();
        } catch { matResult = {error: 'Network ERROR'}; showMat(); }
        return;
      }
      if (key === 'AC') { matResult = null; showMat(); return; }
    }
  }

  // ── BASE-N mode ───────────────────────────────────────────────────────────
  const BASE_HEX_KEY = {
    'LOG':'A','LN':'B','LN':'B','SIN':'C','COS':'D','TAN':'E','FRAC':'F',
  };

  function showBase() {
    let dec = NaN, hexS = '?', binS = '?', octS = '?', decS = '?';
    if (baseResult && !baseResult.error) {
      decS = baseResult.dec;
      hexS = baseResult.hex;
      binS = baseResult.bin;
      octS = baseResult.oct;
    }

    const inputLine = (baseBase === 'HEX' ? baseBase + ': ' : baseBase + ': ') + baseInput + '_';
    let expr, res;
    if (baseResult && !baseResult.error) {
      expr = pad21('DEC: ' + decS) +
             pad21('HEX: ' + hexS) +
             pad21('BIN: ' + (binS.length > 16 ? binS.slice(-16) : binS)) +
             pad21('OCT: ' + octS);
      res  = 'Input(' + baseBase + '):' + baseInput;
    } else {
      expr = pad21('BASE-N [' + baseBase + ']') +
             pad21('Input: ' + baseInput + '_') +
             pad21('F1=DEC F2=HEX') +
             pad21('F3=BIN F4=OCT');
      res  = baseResult && baseResult.error ? baseResult.error : '';
    }

    LCD.render({
      type: 'display', mode: 'BASE', angle: angleMode,
      shift: false, alpha: false,
      expression: expr, result: res, error: '',
      softkeys: Modes.getSoftkeys('BASE'),
    });
  }

  async function handleBaseKey(key) {
    if (key === 'EXIT') { showMenu(); return; }
    if (key === 'F1') { baseBase = 'DEC'; baseInput = ''; baseResult = null; showBase(); return; }
    if (key === 'F2') { baseBase = 'HEX'; baseInput = ''; baseResult = null; showBase(); return; }
    if (key === 'F3') { baseBase = 'BIN'; baseInput = ''; baseResult = null; showBase(); return; }
    if (key === 'F4') { baseBase = 'OCT'; baseInput = ''; baseResult = null; showBase(); return; }
    if (key === 'AC')  { baseInput = ''; baseResult = null; showBase(); return; }
    if (key === 'DEL') { baseInput = baseInput.slice(0, -1); baseResult = null; showBase(); return; }

    // Character input — digits valid for current base + hex letters
    let ch = null;
    if (/^[0-9]$/.test(key)) {
      const allowed = {DEC: 10, HEX: 16, BIN: 2, OCT: 8};
      if (parseInt(key) < allowed[baseBase]) ch = key;
    } else if (baseBase === 'HEX' && BASE_HEX_KEY[key]) {
      ch = BASE_HEX_KEY[key];
    } else if (baseBase === 'HEX') {
      // Try matching key A-F directly (keyboard might send letter keys)
      if (/^[A-F]$/.test(key)) ch = key;
    }
    if (key === 'MINUS') ch = '-';
    if (ch !== null) { baseInput += ch; baseResult = null; showBase(); return; }

    if (key === 'EXE' && baseInput !== '' && baseInput !== '-') {
      try {
        // Convert from current base to all others
        const resp = await fetch('/api/basen/convert', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({value: baseInput, from_base: baseBase, to_base: 'DEC'}),
        });
        const decData = await resp.json();
        if (decData.error) { baseResult = decData; showBase(); return; }

        // Now convert dec to all bases
        const decVal = decData.result;
        const [hexR, binR, octR] = await Promise.all([
          fetch('/api/basen/convert', {method:'POST',headers:{'Content-Type':'application/json'},
            body: JSON.stringify({value: decVal, from_base:'DEC', to_base:'HEX'})}).then(r=>r.json()),
          fetch('/api/basen/convert', {method:'POST',headers:{'Content-Type':'application/json'},
            body: JSON.stringify({value: decVal, from_base:'DEC', to_base:'BIN'})}).then(r=>r.json()),
          fetch('/api/basen/convert', {method:'POST',headers:{'Content-Type':'application/json'},
            body: JSON.stringify({value: decVal, from_base:'DEC', to_base:'OCT'})}).then(r=>r.json()),
        ]);
        baseResult = {dec: decVal, hex: hexR.result, bin: binR.result, oct: octR.result};
        showBase();
      } catch { baseResult = {error: 'Network ERROR'}; showBase(); }
    }
  }

  // ── Master key handler ─────────────────────────────────────────────────────
  function handleKey(key) {
    if (key === 'MENU') { showMenu(); return; }

    if (menuVisible) {
      // Map menu number keys — MAT is key 9 but mode name needs to be 'MAT' not '9'
      const modeKey = MENU_MODE_MAP[key];
      if (modeKey) {
        // Map 'BASE-N' menu entry (key 9 → MAT, not BASE)
        // Real CFX-9850G: 9=MAT, BASE-N is not on main menu (accessed via OPTN)
        // We'll keep spec-compliant: 9=MAT, BASE-N accessible as separate mode
        switchToMode(modeKey === 'MAT' ? 'MAT' : modeKey);
      }
      return;
    }

    switch (appMode) {
      case 'COMP':  handleCompKey(key);     break;
      case 'GRAPH': handleGraphKey(key);    break;
      case 'TABLE': handleTableKey(key);    break;
      case 'STAT':  handleStatKey(key);     break;
      case 'EQUA':  handleEquaKey(key);     break;
      case 'MAT':   handleMatKey(key);      break;
      case 'BASE':  handleBaseKey(key);     break;
      default:
        if (key === 'EXIT') showMenu();
    }
  }

  // ── COMP mode ─────────────────────────────────────────────────────────────
  function handleCompKey(key) {
    if (key === 'EXIT') { showMenu(); return; }
    sendKey(key);
  }

  // ── GRAPH mode ────────────────────────────────────────────────────────────
  function handleGraphKey(key) {
    if (graphSub === 'Y_INPUT') {
      if (key === 'ALPHA') { graphAlpha = !graphAlpha; graphShift = false; showYInput(); return; }
      if (key === 'SHIFT') { graphShift = !graphShift; graphAlpha = false; showYInput(); return; }
      if (key === 'EXE' || key === 'F6') {
        graphAlpha = false; graphShift = false;
        graphFunctions[0] = graphYBuffer;
        graphYBuffer = '';
        drawGraph(); return;
      }
      if (key === 'AC')  { graphAlpha = false; graphShift = false; graphYBuffer = ''; showYInput(); return; }
      if (key === 'DEL') { graphAlpha = false; graphShift = false; graphYBuffer = graphYBuffer.slice(0,-1); showYInput(); return; }
      if (key === 'EXIT') { graphAlpha = false; graphShift = false; graphSub = 'IDLE'; showGraphIdle(); return; }
      let ch;
      if (graphAlpha)      { ch = GRAPH_ALPHA_TEXT[key]; graphAlpha = false; }
      else if (graphShift) { ch = GRAPH_SHIFT_TEXT[key] !== undefined ? GRAPH_SHIFT_TEXT[key] : GRAPH_KEY_TEXT[key]; graphShift = false; }
      else                 { ch = GRAPH_KEY_TEXT[key]; }
      if (ch !== undefined) { graphYBuffer += ch; showYInput(); }
      return;
    }

    if (key === 'EXIT') { showMenu(); return; }
    if (key === 'F1') { graphYBuffer = graphFunctions[0] || ''; showYInput(); return; }
    if (key === 'F2') {
      LCD.render({type:'display', mode:'GRAPH', angle:angleMode, shift:false, alpha:false,
        expression: `Xmin:${graphWindow.xmin} Xmax:${graphWindow.xmax}`,
        result:     `Ymin:${graphWindow.ymin} Ymax:${graphWindow.ymax}`,
        error:'', softkeys: Modes.getSoftkeys('GRAPH')});
      graphSub = 'IDLE'; return;
    }
    if (key === 'F3') {
      graphWindow.xmin *= 0.5; graphWindow.xmax *= 0.5;
      graphWindow.ymin *= 0.5; graphWindow.ymax *= 0.5;
      if (graphSub === 'DRAWN') drawGraph(); return;
    }
    if (key === 'F4') {
      LCD.render({type:'display', mode:'GRAPH', angle:angleMode, shift:false, alpha:false,
        expression:'TRACE: use arrows', result:'', error:'', softkeys: Modes.getSoftkeys('GRAPH')});
      return;
    }
    if (key === 'F6' || key === 'EXE') {
      if (graphFunctions.some(f => f)) drawGraph();
      else { graphYBuffer = ''; showYInput(); }
      return;
    }
    if (key === 'AC') {
      graphSub = 'IDLE'; graphFunctions = ['','','']; graphYBuffer = '';
      showYInput(); return;
    }
    const ch = GRAPH_KEY_TEXT[key];
    if (ch !== undefined) {
      graphYBuffer = graphFunctions[0] || ''; graphYBuffer += ch; showYInput();
    }
  }

  // ── TABLE mode ────────────────────────────────────────────────────────────
  function handleTableKey(key) {
    if (key === 'EXIT') { showMenu(); return; }
    if (key === 'F3') { generateAndShowTable(); return; }
    if (key === 'F1') {
      LCD.render({type:'display', mode:'TABLE', angle:angleMode, shift:false, alpha:false,
        expression:'F(X)=' + tableFn, result:'EXE to confirm', error:'',
        softkeys: Modes.getSoftkeys('TABLE')});
      return;
    }
    if (key === 'F4') { switchToMode('GRAPH'); graphFunctions[0] = tableFn; drawGraph(); return; }
    if (key === 'AC') { tableData = null; tableScroll = 0; showTableIdle(); return; }

    // Scroll table with arrow keys
    if (tableData && tableData.rows) {
      const maxScroll = Math.max(0, tableData.rows.length - 5);
      if (key === 'UP')   { tableScroll = Math.max(0, tableScroll - 1); Graph.renderTable(tableData, tableScroll, 'TABLE', angleMode); return; }
      if (key === 'DOWN') { tableScroll = Math.min(maxScroll, tableScroll + 1); Graph.renderTable(tableData, tableScroll, 'TABLE', angleMode); return; }
    }
  }

  // ── Startup ────────────────────────────────────────────────────────────────
  Keyboard.init(handleKey);
  connect();

  // Boot into MAIN MENU
  showMenu();
})();
