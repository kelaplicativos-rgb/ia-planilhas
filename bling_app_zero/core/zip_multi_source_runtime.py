from __future__ import annotations

import zipfile
from io import BytesIO
from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.html_product_extractor import clean_text, normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/core/zip_multi_source_runtime.py'
PATCH_ATTR = '_mapeiaai_zip_multi_source_runtime_v3_model_safe_detail_coalesce'
SUPPORTED_INNER_SUFFIXES = ('.csv', '.xlsx', '.xls', '.xlsm', '.xlsb', '.txt', '.tsv', '.html', '.htm', '.mht', '.mhtml', '.xml')
KEY_PRIORITY = (
    'sku', 'codigo produto', 'codigo produto *', 'código produto', 'codigo', 'código',
    'codigo sku', 'código sku', 'id produto', 'gtin', 'ean', 'url',
)


def _valid_frame(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def _normalized_frame_signature(df: pd.DataFrame) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    if not _valid_frame(df):
        return (), ()
    frame = df.copy().fillna('').astype(str).reset_index(drop=True)
    columns = tuple(str(column).strip() for column in frame.columns)
    rows = tuple(tuple(str(value).strip() for value in row) for row in frame.loc[:, list(frame.columns)].itertuples(index=False, name=None))
    return columns, rows


def _all_frames_are_equivalent(frames: list[pd.DataFrame]) -> bool:
    valid = [frame for frame in frames if _valid_frame(frame)]
    if len(valid) <= 1:
        return False
    first = _normalized_frame_signature(valid[0])
    if not first[0]:
        return False
    return all(_normalized_frame_signature(frame) == first for frame in valid[1:])


def _key_column(df: pd.DataFrame) -> str:
    if not _valid_frame(df):
        return ''
    columns = list(map(str, df.columns))
    normalized = {normalize_key(column): column for column in columns}
    for key in KEY_PRIORITY:
        wanted = normalize_key(key)
        if wanted in normalized:
            return normalized[wanted]
    for wanted in KEY_PRIORITY:
        wanted_norm = normalize_key(wanted)
        for column in columns:
            if wanted_norm and wanted_norm in normalize_key(column):
                return column
    return ''


def _blank(value: object) -> bool:
    text = clean_text(value).casefold()
    return text in {'', 'nan', 'none', 'null', '<na>'}


def _merge_cell(current: object, candidate: object) -> str:
    current_text = clean_text(current)
    candidate_text = clean_text(candidate)
    if not current_text and candidate_text:
        return candidate_text
    return current_text


def _coalesce_duplicate_rows_by_key(df: pd.DataFrame, key_col: str) -> tuple[pd.DataFrame, int]:
    if not key_col or key_col not in df.columns:
        return df, 0
    with_key = df[df[key_col].map(lambda value: bool(clean_text(value)))].copy().fillna('').astype(str)
    without_key = df[~df[key_col].map(lambda value: bool(clean_text(value)))].copy().fillna('').astype(str)
    if with_key.empty:
        return df, 0

    merged_rows: list[dict[str, str]] = []
    coalesced = 0
    for _key, group in with_key.groupby(key_col, sort=False, dropna=False):
        rows = group.to_dict('records')
        base = {column: clean_text(rows[0].get(column, '')) for column in df.columns}
        if len(rows) > 1:
            coalesced += len(rows) - 1
        for row in rows[1:]:
            for column in df.columns:
                base[column] = _merge_cell(base.get(column, ''), row.get(column, ''))
        merged_rows.append(base)

    merged = pd.DataFrame(merged_rows, columns=list(df.columns)).fillna('').astype(str)
    if not without_key.empty:
        merged = pd.concat([merged, without_key.loc[:, list(df.columns)]], ignore_index=True, sort=False).fillna('').astype(str)
    return merged.reset_index(drop=True), coalesced


def _merge_frames(frames: list[pd.DataFrame], names: list[str]) -> pd.DataFrame:
    prepared: list[pd.DataFrame] = []
    for index, frame in enumerate(frames):
        if not _valid_frame(frame):
            continue
        df = frame.copy().fillna('').astype(str).reset_index(drop=True)
        if 'Arquivo origem' not in df.columns:
            df['Arquivo origem'] = names[index] if index < len(names) else f'arquivo_{index + 1}'
        if 'Página origem' not in df.columns:
            df['Página origem'] = str(index + 1)
        prepared.append(df)
    if not prepared:
        return pd.DataFrame()
    merged = pd.concat(prepared, ignore_index=True, sort=False).fillna('').astype(str)
    key_col = _key_column(merged)
    before = int(len(merged))
    coalesced_duplicates = 0
    if key_col:
        merged, coalesced_duplicates = _coalesce_duplicate_rows_by_key(merged, key_col)
    add_audit_event(
        'zip_multi_source_frames_merged',
        area='ORIGEM',
        status='OK',
        details={
            'frames': len(prepared),
            'rows_before_dedupe': before,
            'rows_after_dedupe': int(len(merged)),
            'coalesced_duplicate_rows': int(coalesced_duplicates),
            'key_column': key_col,
            'adds_provenance_columns': True,
            'detail_rows_fill_blank_values': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return merged.reset_index(drop=True)


def install_zip_multi_source_runtime() -> bool:
    try:
        from bling_app_zero.core import files as files_module
    except Exception as exc:
        add_audit_event('zip_multi_source_runtime_import_failed', area='ORIGEM', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False

    current = getattr(files_module, '_read_zip_bytes', None)
    if getattr(current, PATCH_ATTR, False):
        return False
    original = current

    def patched_read_zip_bytes(data: bytes, file_name: str = 'arquivo.zip') -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        names: list[str] = []
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    inner_name = str(info.filename or '')
                    lower = inner_name.lower()
                    if not lower.endswith(SUPPORTED_INNER_SUFFIXES):
                        continue
                    try:
                        frame = files_module._read_inner_file_bytes(archive.read(info), inner_name)
                    except Exception:
                        frame = pd.DataFrame()
                    if _valid_frame(frame):
                        frames.append(frame.fillna('').astype(str))
                        names.append(inner_name)
        except Exception:
            return pd.DataFrame()

        if len(frames) > 1:
            if _all_frames_are_equivalent(frames):
                add_audit_event(
                    'zip_multi_source_equivalent_files_model_safe',
                    area='ORIGEM',
                    status='OK',
                    details={
                        'files': names,
                        'rows': int(len(frames[0])),
                        'columns': list(map(str, frames[0].columns)),
                        'reason': 'ZIP contem o mesmo modelo em formatos diferentes; nao adicionar Arquivo origem/Pagina origem.',
                        'adds_provenance_columns': False,
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
                return frames[0].copy().fillna('').astype(str).reset_index(drop=True)
            return _merge_frames(frames, names)
        if len(frames) == 1:
            return frames[0].reset_index(drop=True)
        if callable(original):
            try:
                return original(data, file_name)
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

    setattr(patched_read_zip_bytes, PATCH_ATTR, True)
    setattr(files_module, '_read_zip_bytes', patched_read_zip_bytes)
    add_audit_event(
        'zip_multi_source_runtime_installed',
        area='ORIGEM',
        status='OK',
        details={
            'merge_html_mhtml_pages': True,
            'dedupe_by': KEY_PRIORITY,
            'detail_rows_fill_blank_values': True,
            'model_zip_equivalent_files_do_not_receive_provenance_columns': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['install_zip_multi_source_runtime']
