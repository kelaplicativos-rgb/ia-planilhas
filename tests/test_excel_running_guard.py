from __future__ import annotations

from dataclasses import dataclass

from bling_app_zero.core.excel_running_guard import (
    BLANK_ROW_STOP,
    MAX_HEADER_SCAN_COLUMNS,
    _bounded_find_best_excel_header,
    _bounded_frame_from_excel_candidate,
)
from bling_app_zero.core.files import ExcelHeaderCandidate


@dataclass
class _Cell:
    value: object = ''


class _HugeHeaderSheet:
    title = 'Modelo'
    max_row = 1_048_576
    max_column = 16_384

    def __init__(self) -> None:
        self.highest_requested_column = 0

    def cell(self, *, row: int, column: int):
        self.highest_requested_column = max(self.highest_requested_column, column)
        if row == 1 and column == 1:
            return _Cell('Código')
        if row == 1 and column == 2:
            return _Cell('Descrição')
        return _Cell('')


class _HugeDataSheet:
    title = 'Modelo'
    max_row = 1_048_576
    max_column = 16_384

    def __init__(self) -> None:
        self.rows_yielded = 0
        self.requested_max_col = 0

    def iter_rows(self, *, min_row: int, max_row: int, min_col: int, max_col: int, values_only: bool):
        self.requested_max_col = max_col
        self.rows_yielded += 1
        yield ('SKU-1', 'Produto teste')
        for _ in range(BLANK_ROW_STOP + 50):
            self.rows_yielded += 1
            yield ('', '')


class _Workbook:
    def __init__(self, sheet) -> None:
        self.worksheets = [sheet]


def test_header_scan_never_visits_all_excel_columns() -> None:
    sheet = _HugeHeaderSheet()
    candidate = _bounded_find_best_excel_header(_Workbook(sheet))

    assert candidate is not None
    assert candidate.columns == ('Código', 'Descrição')
    assert candidate.max_column == MAX_HEADER_SCAN_COLUMNS
    assert sheet.highest_requested_column <= MAX_HEADER_SCAN_COLUMNS


def test_data_scan_stops_after_long_blank_tail() -> None:
    sheet = _HugeDataSheet()
    candidate = ExcelHeaderCandidate(
        sheet_name='Modelo',
        sheet_index=0,
        header_row=1,
        max_column=2,
        columns=('Código', 'Descrição'),
        positions=(1, 2),
        score=100.0,
        data_rows_below=1,
    )

    frame = _bounded_frame_from_excel_candidate(_Workbook(sheet), candidate)

    assert frame.to_dict(orient='records') == [{'Código': 'SKU-1', 'Descrição': 'Produto teste'}]
    assert sheet.requested_max_col == 2
    assert sheet.rows_yielded == BLANK_ROW_STOP + 1
