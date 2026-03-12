from tkinter import ttk
from tkinter import *
from math import isclose

class SizeError(Exception):
    def __init__(self, message):
        self.message = message


class Layout():
    """A VIS Layout Manager for Frames and Windows"""
    def __init__(self, frame:ttk.Frame|Frame|LabelFrame|Tk|Toplevel):
        self._frame = frame
        self._cells: list[dict] = []
        """Registered widget entries for constraint-enforced placement."""
        self._bound: bool = False
        """Whether the parent <Configure> binding is active."""

        self.row = []
        self.column = []
        self.row_min: list[int] = []
        """Minimum pixel height per row (empty list = no constraints)"""
        self.row_max: list[int] = []
        """Maximum pixel height per row (empty list = no constraints)"""
        self.col_min: list[int] = []
        """Minimum pixel width per column (empty list = no constraints)"""
        self.col_max: list[int] = []
        """Maximum pixel width per column (empty list = no constraints)"""

    def cell(self, row:int, column:int, rowspan:int=None, columnspan:int=None, padding:int=0) -> dict:
        """Return the sizing attributes to place a cell

        Args:
            row (int): The row to place the widget in
            column (int): The column to place the widget in
            rowspan (int): The number of rows to span
            columnspan (int): The number of columns to span
            padding (int): Inward pixel padding applied to all sides of the cell

        Returns:
            relheight (int): The relative height to the parent widget
            relwidth (int): The relative height to the parent widget
            relx (int): The relative x offset within the parent widget
            rely (int): The relative y offset within the parent widget
        """
        if rowspan is None and columnspan is None:
            result = {
                "relwidth": self.column[column],
                "relheight": self.row[row],
                "rely": sum(self.row[:row]),
                "relx": sum(self.column[:column])
            }
        else:
            rowsize=0
            columnsize=0
            if not rowspan is None:
                for i in range(row,row+rowspan,1):
                    rowsize += self.row[i]
            else:
                rowsize = self.row[row]

            if not columnspan is None:
                for i in range(column,column+columnspan,1):
                    columnsize += self.column[i]
            else:
                columnsize = self.column[column]

            result = {
                "relwidth": columnsize,
                "relheight": rowsize,
                "rely": sum(self.row[:row]),
                "relx": sum(self.column[:column])
            }

        if padding:
            result["x"] = padding
            result["y"] = padding
            result["width"] = -2 * padding
            result["height"] = -2 * padding

        return result

    def rowSize(self, rows:list[float|int], minsize:list[int]=None, maxsize:list[int]=None):
        """Sets the size of rows for a Layout

        Args:
            rows (list[float|int]): The size of each individual row from 0.0 to 1.0
            minsize (list[int]): Minimum pixel height per row (optional)
            maxsize (list[int]): Maximum pixel height per row (optional)
        """
        if isclose(sum(rows),1,abs_tol=0.00001):
            if rows[0] == 0:
                self.row=rows
            else:
                self.row=rows
                self.row.insert(0,0)
        else:
            raise SizeError(f"Row sizes must sum to 1.0, not {sum(rows)}")
        self.row_min = minsize if minsize is not None else []
        self.row_max = maxsize if maxsize is not None else []

    def colSize(self, columns:list[float|int], minsize:list[int]=None, maxsize:list[int]=None):
        """Sets the size of columns for a Layout

        Args:
            columns (list[float|int]): The size of each individual column from 0.0 to 1.0
            minsize (list[int]): Minimum pixel width per column (optional)
            maxsize (list[int]): Maximum pixel width per column (optional)
        """
        if isclose(sum(columns),1,abs_tol=0.00001):
            if columns[0] == 0:
                self.column=columns
            else:
                self.column=columns
                self.column.insert(0,0)
        else:
            raise SizeError(f"Column sizes must sum to 1.0, not {sum(columns)}")
        self.col_min = minsize if minsize is not None else []
        self.col_max = maxsize if maxsize is not None else []

    # ── Constraint-enforced placement ──────────────────────────────────────────

    def apply(self, widget, row: int, col: int,
              rowspan: int = None, columnspan: int = None,
              padding: int = 0) -> None:
        """Place *widget* in the layout cell and keep it synchronised on resize.

        Unlike :meth:`cell`, which returns kwargs for a manual ``widget.place()``
        call, ``apply()`` places the widget immediately using absolute pixel
        coordinates and re-places it automatically whenever the parent frame is
        resized, enforcing any ``minsize`` / ``maxsize`` constraints set via
        :meth:`rowSize` and :meth:`colSize`.

        Args:
            widget:      The Tkinter widget to place.
            row:         Row index (1-based, matching the convention of :meth:`cell`).
            col:         Column index (1-based).
            rowspan:     Number of rows to span (default 1).
            columnspan:  Number of columns to span (default 1).
            padding:     Inward pixel padding on all sides.
        """
        entry = {
            "widget": widget, "row": row, "col": col,
            "rowspan": rowspan, "columnspan": columnspan, "padding": padding,
        }
        self._cells.append(entry)
        if not self._bound:
            self._frame.bind("<Configure>", self._on_configure, add="+")
            self._bound = True
        fw = self._frame.winfo_width() or 1
        fh = self._frame.winfo_height() or 1
        self._apply_one(entry, fw, fh)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _row_pixels(self, fh: int) -> list[float]:
        """Return per-element pixel heights for ``self.row`` (including leading 0).

        Min/max constraints are applied element-wise; the leading-zero entry at
        index 0 is never constrained.
        """
        px = [r * fh for r in self.row]
        for i, mn in enumerate(self.row_min):
            idx = i + 1  # skip leading 0
            if idx < len(px):
                px[idx] = max(px[idx], mn)
        for i, mx in enumerate(self.row_max):
            idx = i + 1
            if idx < len(px):
                px[idx] = min(px[idx], mx)
        return px

    def _col_pixels(self, fw: int) -> list[float]:
        """Return per-element pixel widths for ``self.column`` (including leading 0)."""
        px = [c * fw for c in self.column]
        for i, mn in enumerate(self.col_min):
            idx = i + 1
            if idx < len(px):
                px[idx] = max(px[idx], mn)
        for i, mx in enumerate(self.col_max):
            idx = i + 1
            if idx < len(px):
                px[idx] = min(px[idx], mx)
        return px

    def _apply_one(self, entry: dict, fw: int, fh: int) -> None:
        """Place one registered widget using absolute pixel coordinates."""
        row = entry["row"]
        col = entry["col"]
        rowspan = entry["rowspan"] or 1
        colspan = entry["columnspan"] or 1
        padding = entry["padding"]
        widget = entry["widget"]

        row_px = self._row_pixels(fh)
        col_px = self._col_pixels(fw)

        x0 = int(sum(col_px[:col]))
        y0 = int(sum(row_px[:row]))
        cw = int(sum(col_px[col: col + colspan]))
        ch = int(sum(row_px[row: row + rowspan]))

        if padding:
            widget.place(x=x0 + padding, y=y0 + padding,
                         width=cw - 2 * padding, height=ch - 2 * padding)
        else:
            widget.place(x=x0, y=y0, width=cw, height=ch)

    def _on_configure(self, event) -> None:
        """Re-place all registered widgets when the parent frame is resized."""
        fw, fh = event.width, event.height
        for entry in self._cells:
            self._apply_one(entry, fw, fh)
