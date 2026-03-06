"""Parser for Casio FA-122/FA-123/FA-124 CAT file format (.cat files).

CAT files are ASCII text files produced by Casio's PC-link software.
A single .cat file can hold multiple records (programs, matrices, etc.).

Record structure:
    %Header Record
    Format:TXT
    Communication SW:0
    Data Type:PG          (PG = program; MT = matrix; other types are skipped)
    Capacity:NNNN
    File Name:PROGNAME    (may contain backslash tokens, e.g. P\\theta)
    ...
    %Data Record
    \\Cls
    0\\->A~Z
    \\Lbl 0
    ...
    %End                  (or %End Record)

Token conventions in the data section:
  \\->      →    store / assignment arrow
  \\=>      ⇒    single-line conditional (cond ⇒ stmt)
  \\Goto    immediately followed by label (no space): \\GotoN → Goto N
  \\(-)     unary minus  (−4 written as \\(-)4)
  \\aster   *    asterisk character
  \\slash   /    forward-slash character
  \\<=      ≤    less-than-or-equal
  \\>=      ≥    greater-than-or-equal
  \\<>      ≠    not-equal
  \\theta   θ
  \\pi      π
  \\Disp    ◢    display-pause
  All other backslash-prefixed identifiers: strip the backslash.

The \\  prefix ALSO acts as a statement separator in many programs, so
statement-level commands are replaced with newline + command so that
multi-statement lines are split correctly.
"""

import re


# ── Public API ────────────────────────────────────────────────────────────────

def is_cat_file(content: str) -> bool:
    """Return True if *content* looks like a CAT-format file."""
    stripped = content.lstrip('\r\n\ufeff ')
    return stripped.startswith('%Header Record')


def parse_cat_file(content: str) -> tuple[str, str]:
    """Parse a CAT file and return (primary_program_name, program_source).

    Only the *first* PG record is returned as source.  Use
    ``parse_cat_programs`` to get all programs from a multi-record file.
    """
    programs = parse_cat_programs(content)
    if programs:
        return programs[0]
    return ('PROGRAM', '')


def parse_cat_programs(content: str) -> list[tuple[str, str]]:
    """Parse ALL program (Data Type:PG) records from a CAT file.

    Returns a list of (name, source) tuples in file order.
    Non-program records (matrices, pictures, etc.) are silently skipped.
    """
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines   = content.split('\n')

    results: list[tuple[str, str]] = []

    i = 0
    while i < len(lines):
        if lines[i].strip() == '%Header Record':
            name, data_type, data_lines, i = _parse_one_record(lines, i + 1)
            if data_type == 'PG' and data_lines is not None:
                source = cat_to_source('\n'.join(data_lines))
                results.append((name, source))
        else:
            i += 1

    return results


# ── Internal record parser ────────────────────────────────────────────────────

def _parse_one_record(lines: list[str], start: int) -> tuple[str, str, list[str] | None, int]:
    """Parse one record starting at *start*.

    Returns (name, data_type, data_lines_or_None, next_line_index).
    data_lines is None for non-PG records.
    """
    name      = 'PROGRAM'
    data_type = ''
    data_lines: list[str] | None = None
    in_data   = False
    i         = start

    while i < len(lines):
        stripped = lines[i].strip()

        if stripped == '%Data Record':
            in_data = True
            data_lines = []
            i += 1
            continue

        if stripped.startswith('%End'):
            i += 1
            break

        if stripped == '%Header Record':
            # Start of next record — stop here (do NOT consume this line)
            break

        if not in_data:
            if stripped.startswith('File Name:'):
                raw = stripped[len('File Name:'):].strip()
                # Decode backslash tokens in the name itself (e.g. P\theta → Pθ)
                name = _decode_name_tokens(raw) if raw else 'PROGRAM'
            elif stripped.startswith('Data Type:'):
                data_type = stripped[len('Data Type:'):].strip()
        else:
            if data_lines is not None:
                data_lines.append(lines[i])

        i += 1

    return name, data_type, data_lines, i


def _decode_name_tokens(s: str) -> str:
    """Decode backslash tokens that can appear in a File Name field."""
    s = s.replace('\\theta', 'θ').replace('\\Theta', 'θ')
    s = s.replace('\\pi', 'π').replace('\\PI', 'π')
    s = s.replace('\\r', 'r')
    return s


# ── Token conversion ──────────────────────────────────────────────────────────
#
# Statement-level commands are converted to  \n + command  so that lines
# like  \Line\Disp\ClrText  split into three separate statements.
#
# Expression-level commands (math functions, keywords within For/If, etc.)
# just have the backslash stripped.

_STMT_COMMANDS: list[str] = [
    # Mode / display settings
    'AxesOff', 'AxesOn', 'GridOff', 'GridOn', 'LabelOff', 'LabelOn',
    'Norm', 'Fix', 'Sci', 'Deg', 'Rad', 'Gra',
    # Screen
    'ViewWindow', 'ClrText', 'ClrGraph', 'ClrList', 'Cls',
    'DispGraph', 'DrawGraph', 'DrawStat',
    # Text / graphics commands (each starts a new statement)
    'Locate', 'Getkey', 'Text', 'Circle',
    'PxlOn', 'PxlOff', 'PxlChg', 'PxlTest',
    'PlotOn', 'PlotOff', 'PlotChg', 'Plot',
    'F-Line', 'Line',
    # Control flow
    'Lbl', 'For', 'Next', 'While', 'WhileEnd', 'Do', 'LpWhile',
    'If', 'Then', 'Else', 'IfEnd',
    'Return', 'Stop', 'Break',
    # I/O
    'Input', 'Print',
    # Sub-programs
    'Prog',
    # Data
    'Dim', 'Fill', 'SortA', 'SortD',
    # Color (pass through; interpreter treats as no-ops)
    'Orange', 'Green', 'Blue',
    # Dsz / Isz (decrement/increment-and-skip)
    'Dsz', 'Isz',
]

_EXPR_COMMANDS: list[str] = [
    # For-loop sub-keywords (stay on the same line as For)
    'To', 'Step',
    # Math functions
    'Int', 'Frac', 'Abs', 'Sgn', 'Sqrt', 'Log', 'Ln', 'Exp',
    'Sin', 'Cos', 'Tan', 'Asin', 'Acos', 'Atan',
    'Sinh', 'Cosh', 'Tanh',
    'Pol', 'Rec', 'Solve', 'FMin', 'FMax',
    # Data
    'List', 'Mat', 'Seq', 'Sum', 'Prod', 'Mean', 'Median',
    'Augment', 'Trn', 'Det',
    # Logic operators
    'And', 'Or', 'Not', 'Xor',
    # Misc
    'Ans', 'Ran',
]

# Sort longest first to avoid partial matches (e.g. "WhileEnd" before "While")
_STMT_COMMANDS.sort(key=len, reverse=True)
_EXPR_COMMANDS.sort(key=len, reverse=True)


def cat_to_source(cat_text: str) -> str:
    """Convert CAT-format program text to plain-text CAS interpreter format."""

    # ── Pre-processing: strip single-quote comments ───────────────────────────
    # Lines starting with ' are comments in Casio BASIC.
    # Process per-line so we don't strip ' inside strings.
    cleaned_lines = []
    for line in cat_text.split('\n'):
        stripped = line.strip()
        if stripped.startswith("'"):
            continue   # skip comment line entirely
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # ── Step 1: special two-char / multi-char operators ───────────────────────
    text = text.replace('\\->', '→')           # store arrow
    text = text.replace('\\=>', '⇒')           # single-line conditional
    text = text.replace('\\<=', '<=')          # ≤
    text = text.replace('\\>=', '>=')          # ≥
    text = text.replace('\\<>', '<>')          # ≠  (handled in eval_cond)
    text = text.replace('\\(-)', '-')          # unary minus

    # ── Step 2: special symbol tokens ─────────────────────────────────────────
    text = text.replace('\\aster', '*')
    text = text.replace('\\slash', '/')
    text = text.replace('\\theta', 'θ')
    text = text.replace('\\Theta', 'θ')
    text = text.replace('\\pi',    'π')
    text = text.replace('\\PI',    'π')
    text = text.replace('\\Ran#',  'Ran#')

    # ── Step 3: \Goto followed immediately by label (no space) ───────────────
    # Handle Greek-letter labels first (e.g. \Goto\theta already resolved above)
    text = re.sub(r'\\Goto\s*θ\b', 'Goto θ', text)
    text = re.sub(r'\\Goto\s*r\b', 'Goto r', text)
    text = re.sub(r'\\Goto([A-Za-z0-9])', r'Goto \1', text)

    # ── Step 4: \Disp → statement-separator + ◢ ──────────────────────────────
    # \Disp is the display-pause (◢) and also acts as a statement boundary.
    # Use \n◢\n so that content following \Disp on the same raw line
    # (e.g. G=6⇒Prog "PT") lands on its own line and is not merged with ◢.
    text = text.replace('\\Disp', '\n◢\n')

    # ── Step 5: statement-level commands → newline + command ─────────────────
    for cmd in _STMT_COMMANDS:
        text = text.replace(f'\\{cmd}', f'\n{cmd}')

    # ── Step 6: expression-level commands → strip backslash ──────────────────
    for cmd in _EXPR_COMMANDS:
        text = text.replace(f'\\{cmd}', cmd)

    # ── Step 7: single uppercase variable letters ─────────────────────────────
    text = re.sub(r'\\([A-Z])\b', r'\1', text)

    # ── Step 8: \r as polar variable r ────────────────────────────────────────
    text = re.sub(r'\\r\b', 'r', text)

    # ── Step 9: A~Z range assignments ─────────────────────────────────────────
    text = _expand_range_assign(text)

    # ── Step 10: clean up remaining stray backslashes ─────────────────────────
    # `\ ` (backslash-space) appears before `Or`, `And`, etc. in conditions.
    # After all named-token substitutions these are just whitespace separators.
    text = text.replace('\\ ', ' ')
    # Strip any other remaining `\` not followed by a letter/digit/newline
    text = re.sub(r'\\(?=[^A-Za-z0-9\n])', '', text)

    # ── Step 11: rejoin lines whose continuation was split to the next line ────
    # Statement-level splitting (step 5) can break patterns like:
    #   \Getkey=31\=>\Prog "TETMAIN"  → "Getkey=31⇒" / "Prog …" (separate)
    #   \LpWhile\Getkey<>31           → "LpWhile"    / "Getkey<>31" (separate)
    #   \While\Getkey<>31             → "While"      / "Getkey<>31" (separate)
    #   \If\Getkey=31                 → "If"         / "Getkey=31" (separate)
    # Rejoin these by appending the next non-empty line.
    _NEEDS_CONTINUATION = re.compile(
        r'^(.*⇒|LpWhile\s*|While\s*|If\s*)$', re.IGNORECASE
    )
    lines  = text.split('\n')
    joined: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip()
        if _NEEDS_CONTINUATION.match(stripped):
            # Find next non-blank line to use as the continuation
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                # ⇒ lines join without extra space; control keywords need a space
                sep = '' if stripped.endswith('⇒') else ' '
                joined.append(stripped + sep + lines[j].strip())
                i = j + 1
                continue
        joined.append(line)
        i += 1
    text = '\n'.join(joined)

    return text


# ── Range assignment expansion ────────────────────────────────────────────────

def _expand_range_assign(text: str) -> str:
    """Expand  value→A~Z  into individual per-variable lines."""
    lines = text.split('\n')
    out: list[str] = []
    for line in lines:
        out.extend(_try_expand_range(line))
    return '\n'.join(out)


def _try_expand_range(line: str) -> list[str]:
    """If *line* is  expr→START~END  return expanded list, else [line]."""
    m = re.match(r'^(.+?)→([A-Z])~([A-Z])\s*$', line.strip())
    if not m:
        return [line]
    value, start, end = m.group(1), m.group(2), m.group(3)
    if ord(start) > ord(end):
        return [line]
    return [f'{value}→{chr(v)}' for v in range(ord(start), ord(end) + 1)]


# ── Matrix record parser ─────────────────────────────────────────────────────

def parse_cat_matrices(content: str) -> list[tuple[str, list[list[float]]]]:
    """Parse all matrix (Data Type:MT) records from a CAT file.

    Returns a list of (letter, data) where *letter* is the single-letter matrix
    name (e.g. 'A' for 'Mat A') and *data* is a list of rows (list of floats).
    """
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines   = content.split('\n')
    results: list[tuple[str, list[list[float]]]] = []

    i = 0
    while i < len(lines):
        if lines[i].strip() != '%Header Record':
            i += 1
            continue
        # Scan record header and data
        data_type = ''
        mat_letter = ''
        rows = 0
        cols = 0
        in_data  = False
        val_lines: list[str] = []
        i += 1
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith('%End') or s == '%Header Record':
                break
            if s == '%Data Record':
                in_data = True
            elif not in_data:
                if s.startswith('Data Type:'):
                    data_type = s[len('Data Type:'):].strip()
                elif s.startswith('Variable Name:'):
                    raw = s[len('Variable Name:'):].strip()
                    # "Mat A" → 'A'
                    if raw.upper().startswith('MAT '):
                        mat_letter = raw[4:].strip().upper()
                    else:
                        mat_letter = raw.upper()
                elif s.startswith('Rows:'):
                    try: rows = int(s[len('Rows:'):].strip())
                    except ValueError: pass
                elif s.startswith('Columns:'):
                    try: cols = int(s[len('Columns:'):].strip())
                    except ValueError: pass
            else:
                val_lines.append(s)
            i += 1

        if data_type == 'MT' and mat_letter and rows > 0 and cols > 0:
            mat: list[list[float]] = [[0.0] * cols for _ in range(rows)]
            for vl in val_lines:
                m = re.match(r'Value\s*:\s*(\d+)\s+(\d+)\s+([\d.eE+\-]+)', vl)
                if m:
                    r, c, v = int(m.group(1)), int(m.group(2)), float(m.group(3))
                    if 1 <= r <= rows and 1 <= c <= cols:
                        mat[r - 1][c - 1] = v
            results.append((mat_letter, mat))

    return results


# ── Entry point detection ──────────────────────────────────────────────────────

_PROG_CALL_RE = re.compile(r'Prog\s+"([^"]+)"', re.IGNORECASE)


def find_entry_point(programs: list[tuple[str, str]]) -> str:
    """Return the name of the entry-point program in a multi-record CAT file.

    The entry point is the program whose name is *not* referenced by any
    ``Prog "name"`` call in any other program in the set.  If all programs
    reference each other (circular) the last program in file order is used,
    as Casio convention places the title/entry program last.
    """
    if not programs:
        return 'PROGRAM'
    if len(programs) == 1:
        return programs[0][0]

    # Collect all names called by Prog "..." anywhere in the file
    referenced: set[str] = set()
    for _, src in programs:
        for m in _PROG_CALL_RE.finditer(src):
            referenced.add(m.group(1))

    # Entry point = a program not called by anyone else
    for name, _ in programs:
        if name not in referenced:
            return name

    # All referenced (circular) — last program in file order is the entry
    return programs[-1][0]
