from __future__ import annotations

import zipfile
from io import BytesIO
from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.html_product_extractor import clean_text, normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/core/zip_multi_source_runtime.py'
PATCH_ATTR = '_mapeiaai_zip_multi_source_runtime_v2_model_safe'
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
    if key_col:
        non_empty = merged[key_col].map(lambda value: bool(clean_text(value)))
        with_key = merged[non_empty].drop_duplicates(subset=[key_col], keep='first')
        without_key = merged[~non_empty]
        merged = pd.concat([with_key, without_key], ignore_index=True, sort=False).fillna('').astype(str)
    add_audit_event(
        'zip_multi_source_frames_merged',
        area='ORIGEM',
        status='OK',
        details={
            'frames': len(prepared),
            'rows_before_dedupe': before,
            'rows_after_dedupe': int(len(merged)),
            'key_column': key_col,
            'adds_provenance_columns': True,
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
            'model_zip_equivalent_files_do_not_receive_provenance_columns': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['install_zip_multi_source_runtime']
