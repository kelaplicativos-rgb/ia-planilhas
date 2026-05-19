from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_shared import read_upload_fast

MODEL_SPREADSHEET_TYPES = ['xlsx', 'xls', 'csv', 'xlsm', 'xlsb']


@dataclass
class ModelUploadResult:
    cadastro_model_file: Any | None = None
    cadastro_model_df: pd.DataFrame | None = None
    estoque_model_file: Any | None = None
    estoque_model_df: pd.DataFrame | None = None
    model_file: Any | None = None
    model_df: pd.DataFrame | None = None
    attachments: list[Any] | None = None
    ignored_files: list[Any] | None = None


def _file_name(file: Any | None) -> str:
    return str(getattr(file, 'name', 'arquivo')).strip() if file is not None else ''


def _file_ext(file: Any | None) -> str:
    name = _file_name(file).lower()
    return name.rsplit('.', 1)[-1] if '.' in name else ''


def _file_audit_info(file: Any | None) -> dict[str, Any] | None:
    if file is None:
        return None
    return {
        'name': _file_name(file),
        'extension': _file_ext(file),
        'size': getattr(file, 'size', None),
        'type': getattr(file, 'type', None),
    }


def _df_audit_info(df: pd.DataFrame | None) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        return {'valid': False}
    return {
        'valid': True,
        'rows': int(len(df)),
        'columns_count': int(len(df.columns)),
        'columns': [str(column) for column in list(df.columns)[:120]],
    }


def _safe_read(file: Any) -> pd.DataFrame | None:
    try:
        df = read_upload_fast(file)
        add_audit_event(
            'destination_model_file_read',
            area='MODELO',
            details={'file': _file_audit_info(file), 'dataframe': _df_audit_info(df)},
        )
        return df
    except Exception as exc:
        add_audit_event(
            'destination_model_file_read_failed',
            area='MODELO',
            status='ERRO',
            details={'file': _file_audit_info(file), 'error': str(exc)},
        )
        return None


def _valid_model(df: pd.DataFrame | None) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def _pick_destination_model(loaded: list[tuple[Any, pd.DataFrame | None]]) -> tuple[Any | None, pd.DataFrame | None]:
    for file, df in loaded:
        if _valid_model(df):
            return file, df.copy().fillna('')
    return None, None


def _columns_caption(df: pd.DataFrame, limit: int = 18) -> str:
    columns = [str(column) for column in list(df.columns)[:limit]]
    suffix = '...' if len(df.columns) > limit else ''
    return ', '.join(columns) + suffix


def _render_model_summary(file: Any | None, df: pd.DataFrame | None) -> None:
    if not isinstance(df, pd.DataFrame):
        return
    st.success('Modelo de destino anexado.')
    st.caption(f'{_file_name(file)} · {len(df)} linha(s) · {len(df.columns)} coluna(s)')
    with st.expander('Ver colunas do modelo de destino', expanded=False):
        st.caption(_columns_caption(df))


def render_model_upload_box(
    title: str,
    operation: str,
    key: str,
    required_model: bool = False,
    caption: str | None = None,
) -> ModelUploadResult:
    files = st.file_uploader(
        'Enviar modelo de destino',
        type=None,
        accept_multiple_files=True,
        key=key,
        help='Envie a planilha modelo que será preenchida no final. Ela precisa ter cabeçalho com os nomes das colunas.',
        label_visibility='collapsed',
    )

    if not files:
        return ModelUploadResult(attachments=[], ignored_files=[])

    selected_files = list(files)
    supported_files = [file for file in selected_files if _file_ext(file) in MODEL_SPREADSHEET_TYPES]
    ignored_files = [file for file in selected_files if _file_ext(file) not in MODEL_SPREADSHEET_TYPES]

    add_audit_event(
        'destination_model_upload_received',
        area='MODELO',
        details={
            'title': title,
            'operation': operation,
            'key': key,
            'required_model': required_model,
            'caption': caption,
            'supported_count': len(supported_files),
            'ignored_count': len(ignored_files),
            'files': [_file_audit_info(file) for file in selected_files],
            'model_policy': 'first_valid_spreadsheet_is_destination_contract',
        },
    )

    if not supported_files:
        st.warning('Nenhuma planilha compatível encontrada. Use XLSX, XLS, CSV, XLSM ou XLSB.')
        return ModelUploadResult(attachments=[], ignored_files=ignored_files)

    with st.spinner('Lendo modelo de destino...'):
        loaded = [(file, _safe_read(file)) for file in supported_files]
        destination_file, destination_df = _pick_destination_model(loaded)

    if not _valid_model(destination_df):
        st.warning(
            'Não encontrei colunas válidas nesse arquivo. '
            'Verifique se a planilha possui cabeçalho na primeira linha ou envie o modelo correto que será preenchido no final.'
        )
        return ModelUploadResult(attachments=supported_files, ignored_files=ignored_files)

    add_audit_event(
        'destination_model_selected',
        area='MODELO',
        status='OK',
        details={
            'selected_model_file': _file_audit_info(destination_file),
            'selected_df': _df_audit_info(destination_df),
            'model_policy': 'generic_destination_contract',
        },
    )
    _render_model_summary(destination_file, destination_df)

    return ModelUploadResult(
        cadastro_model_file=destination_file,
        cadastro_model_df=destination_df,
        estoque_model_file=None,
        estoque_model_df=None,
        model_file=destination_file,
        model_df=destination_df,
        attachments=supported_files,
        ignored_files=ignored_files,
    )


__all__ = ['MODEL_SPREADSHEET_TYPES', 'ModelUploadResult', 'render_model_upload_box']
