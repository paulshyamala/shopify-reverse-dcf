"""Insert rows in one tab and keep every reference in the workbook pointing at the same cells.

openpyxl's insert_rows does not update formulas. insert_rows() here:
1. rewrites every formula in every tab that refers to the target tab's rows at or
   below the insertion point (same-tab references in the target tab, "Tab!A1"
   references anywhere else), including both ends of ranges,
2. moves the target tab's cells (values, styles, comments) down n rows,
3. shifts the target tab's data-validation ranges.
It refuses to run on a tab with conditional formatting or merged cells (not handled).
"""

import re
from copy import copy

from openpyxl.comments import Comment
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange

# Optional sheet prefix (bare or quoted), a cell, optionally ":cell" for a range; $ anchors kept
CELL = r"\$?[A-Z]{1,3}\$?\d+"
REF = re.compile(rf"(?:(?P<sheet>'[^']+'|[A-Za-z_][A-Za-z0-9_]*)!)?(?P<a>{CELL})(?::(?P<b>{CELL}))?(?![\d(A-Za-z_])")
ROW = re.compile(r"(\d+)$")
STRING = re.compile(r'"[^"]*"')


def _shift_formula(formula, own_sheet, target, at, n):
    """Shift references to target-tab rows >= at by n (both ends of a range)."""
    strings = [(s.start(), s.end()) for s in STRING.finditer(formula)]

    def bump(cell):
        row = int(ROW.search(cell).group(1))
        return ROW.sub(str(row + n), cell) if row >= at else cell

    def sub(m):
        if any(a <= m.start() < b for a, b in strings):
            return m.group(0)
        sheet = (m.group("sheet") or "").strip("'") or own_sheet
        if sheet != target:
            return m.group(0)
        prefix = f"{m.group('sheet')}!" if m.group("sheet") else ""
        return prefix + bump(m.group("a")) + (f":{bump(m.group('b'))}" if m.group("b") else "")

    return REF.sub(sub, formula)


def insert_rows(wb, target, at, n):
    ws = wb[target]
    if list(ws.conditional_formatting) or ws.merged_cells.ranges:
        raise ValueError(f"{target}: conditional formatting / merged cells not supported")
    changed = 0
    for sheet in wb:
        for row in sheet.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    new = _shift_formula(c.value, sheet.title, target, at, n)
                    if new != c.value:
                        c.value, changed = new, changed + 1
    last, ncols = ws.max_row, ws.max_column
    for r in range(last, at - 1, -1):
        for col in range(1, ncols + 1):
            src, dst = ws.cell(r, col), ws.cell(r + n, col)
            dst.value, dst._style = src.value, copy(src._style)
            dst.comment = Comment(src.comment.text, src.comment.author) if src.comment else None
            if src.comment:
                dst.comment.width, dst.comment.height = src.comment.width, src.comment.height
    for r in range(at, at + n):
        for col in range(1, ncols + 1):
            c = ws.cell(r, col)
            c.value, c.comment = None, None
            c.style = "Normal"
    for dv in ws.data_validations.dataValidation:
        dv.sqref = MultiCellRange([CellRange(min_col=g.min_col, max_col=g.max_col,
                                             min_row=g.min_row + (n if g.min_row >= at else 0),
                                             max_row=g.max_row + (n if g.max_row >= at else 0))
                                   for g in dv.sqref.ranges])
    return changed
