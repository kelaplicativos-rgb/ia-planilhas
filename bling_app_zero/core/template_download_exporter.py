from __future__ import annotations

from copy import copy
from io import BytesIO
from typing import Any

import pandas as pd

try:
    from openpyxl import load_workbook
except Exception:  # pragma: no cover
    load_workbook = None

SUPPORTED_TEMPLATE_EXTENSIONS = {'xlsx', 'xlsm'}
DEFAULT_HEADER_SCAN_ROWS = 30


def _normalize(value: object) -> str:
    return ' '.join(str(value or '').replace('\ufeff', '').replace('\xa0', ' ').split()).strip().lower()


def _template_extension(file_name: str) -> str:
    name = str(file_name or '').lower().strip()
    return name.rsplit('.', 1)[-1] if '.' in name else ''


def can_export_from_template(file_name: str | None, file_bytes: bytes | None) -> bool:
    if not file_name or not file_bytes:
        return False
    return _template_extension(file_name) in SUPPORTED_TEMPLATE_EXTENSIONS and callable(load_workbook)


def output_name_for_template(file_name: str | None) -> str:
    name = str(file_name or 'modelo_preenchido.xlsx').strip() or 'modelo_preenchido.xlsx'
    if '.' not in name:
        return f'{name}_preenchido.xlsx'
    stem, ext = name.rsplit('.', 1)
    return f'{stem}_preenchido.{ext}'


def _safe_cell_text(value: object) -> str:
    return ' '.join(str(value or '').replace('\ufeff', '').replace('\xa0', ' ').split()).strip()


def _find_header_row(ws: Any, columns: list[str]) -> int:
    wanted = {_normalize(column) for column in columns if _normalize(column)}
    if not wanted:
        return 1

    best_row = 1
    best_score = -1
    max_scan = min(max(ws.max_row or 1, 1), DEFAULT_HEADER_SCAN_ROWS)

    for row_index in range(1, max_scan + 1):
        row_values = {_normalize(ws.cell(row=row_index, column=col_index).value) for col_index in range(1, (ws.max_column or 1) + 1)}
        score = len(wanted & row_values)
        if score > best_score:
            best_score = score
            best_row = row_index

    return best_row


def _build_column_positions(ws: Any, header_row: int, columns: list[str]) -> dict[str, int]:
    by_normalized_header: dict[str, int] = {}
    for col_index in range(1, (ws.max_column or 1) + 1):
        value = _normalize(ws.cell(row=header_row, column=col_index).value)
        if value and value not in by_normalized_header:
            by_normalized_header[value] = col_index

    positions: dict[str, int] = {}
    for column in columns:
        key = _normalize(column)
        if key in by_normalized_header:
            positions[column] = by_normalized_header[key]

    return positions


def _copy_row_style(ws: Any, source_row: int, target_row: int) -> None:
    if source_row <= 0 or target_row <= 0 or source_row == target_row:
        return

    try:
        ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height
        ws.row_dimensions[target_row].hidden = ws.row_dimensions[source_row].hidden
        ws.row_dimensions[target_row].outlineLevel = ws.row_dimensions[source_row].outlineLevel
    except Exception:
        pass

    for col_index in range(1, (ws.max_column or 1) + 1):
        source = ws.cell(row=source_row, column=col_index)
        target = ws.cell(row=target_row, column=col_index)
        if source.has_style:
            target._style = copy(source._style)
        if source.number_format:
            target.number_format = source.number_format
        if source.font:
            target.font = copy(source.font)
        if source.fill:
            target.fill = copy(source.fill)
        if source.border:
            target.border = copy(source.border)
        if source.alignment:
            target.alignment = copy(source.alignment)
        if source.protection:
            target.protection = copy(source.protection)


def _write_dataframe_to_sheet(ws: Any, df: pd.DataFrame) -> tuple[int, int]:
    columns = [str(column) for column in df.columns]
    header_row = _find_header_row(ws, columns)
    positions = _build_column_positions(ws, header_row, columns)
    first_data_row = header_row + 1
    template_data_row = first_data_row if ws.max_row >= first_data_row else header_row
    total_rows = len(df)
    last_needed_row = first_data_row + max(total_rows - 1, 0)
    max_existing_row = max(ws.max_row or first_data_row, last_needed_row)

    for row_index in range(first_data_row, last_needed_row + 1):
        if row_index > (ws.max_row or 0):
            _copy_row_style(ws, template_data_row, row_index)

    for row_offset, (_, row) in enumerate(df.fillna('').iterrows()):
        excel_row = first_data_row + row_offset
        if excel_row > (ws.max_row or 0):
            _copy_row_style(ws, template_data_row, excel_row)
        for column, col_index in positions.items():
            ws.cell(row=excel_row, column=col_index).value = '' if pd.isna(row[column]) else row[column]

    for excel_row in range(first_data_row + total_rows, max_existing_row + 1):
        for col_index in positions.values():
            ws.cell(row=excel_row, column=col_index).value = None

    return header_row, len(positions)


def build_template_download_bytes(
    *,
    template_bytes: bytes,
    template_name: str,
    df: pd.DataFrame,
) -> bytes:
    if not can_export_from_template(template_name, template_bytes):
        raise ValueError('Modelo XLSX/XLSM indisponível para exportação fiel.')
    if not isinstance(df, pd.DataFrame):
        raise ValueError('DataFrame final inválido.')

    keep_vba = _template_extension(template_name) == 'xlsm'
    workbook = load_workbook(BytesIO(template_bytes), keep_vba=keep_vba)
    worksheet = workbook.active
    _write_dataframe_to_sheet(worksheet, df.copy().fillna(''))

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


__all__ = [
    'SUPPORTED_TEMPLATE_EXTENSIONS',
    'build_template_download_bytes',
    'can_export_from_template',
    'output_name_for_template',
]
