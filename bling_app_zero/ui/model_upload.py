from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_shared import read_upload_fast
from bling_app_zero.universal.model_contract_detector import (
    MODEL_CONTRACT_CONFIDENCE_KEY,
    MODEL_CONTRACT_LABEL_KEY,
    MODEL_CONTRACT_REASON_KEY,
    MODEL_CONTRACT_TYPE_KEY,
    detect_model_contract,
)

MODEL_SPREADSHEET_TYPES = ['xlsx', 'xls', 'csv', 'xlsm', 'xlsb']
EXCEL_HEADER_FALLBACK_TYPES = {'xlsx', 'xlsm'}


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
    contract_type: str = 'universal'
    contract_label: str = 'Modelo de destino'
    contract_confidence: float = 0.0
    contract_reason: str = ''


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


def _clean_header_value(value: Any) -> str:
    text = str(value or '').replace('\ufeff', '').strip()
    text = ' '.join(text.split())
    return text


def _dedupe_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    fixed: list[str] = []
    for index, column in enumerate(columns):
        base = _clean_header_value(column) or f'Coluna {index + 1}'
        count = seen.get(base, 0)
        seen[base] = count + 1
        fixed.append(base if count == 0 else f'{base} ({count + 1})')
    return fixed


def _read_excel_header_fallback(file: Any) -> pd.DataFrame | None:
    """Recupera cabeçalho de modelos XLSX/XLSM sem linhas."""
    if _file_ext(file) not in EXCEL_HEADER_FALLBACK_TYPES:
        return None

    try:
        from openpyxl import load_workbook

        file_bytes = file.getvalue()
        workbook = load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
        best_columns: list[str] = []
        best_sheet = ''

        for sheet in workbook.worksheets:
            max_rows_to_scan = min(int(sheet.max_row or 1), 10)
            max_cols_to_scan = int(sheet.max_column or 0)
            if max_cols_to_scan <= 0:
                continue

            for row_index in range(1, max_rows_to_scan + 1):
                values = [sheet.cell(row=row_index, column=col_index).value for col_index in range(1, max_cols_to_scan + 1)]
                columns = [_clean_header_value(value) for value in values]
                columns = [column for column in columns if column]
                if len(columns) > len(best_columns):
                    best_columns = columns
                    best_sheet = sheet.title

        try:
            workbook.close()
        except Exception:
            pass

        if not best_columns:
            add_audit_event('destination_model_header_fallback_empty', area='MODELO', status='AVISO', details={'file': _file_audit_info(file)})
            return None
        df = pd.DataFrame(columns=_dedupe_columns(best_columns))
        add_audit_event(
            'destination_model_header_fallback_applied',
            area='MODELO',
            status='OK',
            details={
                'file': _file_audit_info(file),
                'sheet': best_sheet,
                'dataframe': _df_audit_info(df),
                'reason': 'reader_returned_without_columns_or_header_only_model',
            },
        )
        return df
    except Exception as exc:
        add_audit_event('destination_model_header_fallback_failed', area='MODELO', status='ERRO', details={'file': _file_audit_info(file), 'error': str(exc)})
        return None


def _safe_read(file: Any) -> pd.DataFrame | None:
    try:
        df = read_upload_fast(file)
        if not _valid_model(df):
            fallback_df = _read_excel_header_fallback(file)
            if _valid_model(fallback_df):
                df = fallback_df
        add_audit_event('destination_model_file_read', area='MODELO', details={'file': _file_audit_info(file), 'dataframe': _df_audit_info(df)})
        return df
    except Exception as exc:
        fallback_df = _read_excel_header_fallback(file)
        if _valid_model(fallback_df):
            add_audit_event(
                'destination_model_file_read_recovered_by_header_fallback',
                area='MODELO',
                status='OK',
                details={'file': _file_audit_info(file), 'dataframe': _df_audit_info(fallback_df), 'original_error': str(exc)},
            )
            return fallback_df
        add_audit_event('destination_model_file_read_failed', area='MODELO', status='ERRO', details={'file': _file_audit_info(file), 'error': str(exc)})
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


def _remember_contract_detection(detection) -> None:
    st.session_state[MODEL_CONTRACT_TYPE_KEY] = detection.contract_type
    st.session_state[MODEL_CONTRACT_LABEL_KEY] = detection.label
    st.session_state[MODEL_CONTRACT_CONFIDENCE_KEY] = float(detection.confidence)
    st.session_state[MODEL_CONTRACT_REASON_KEY] = detection.reason
    st.session_state['home_detected_operation'] = detection.contract_type
    st.session_state['operacao_final'] = detection.contract_type
    st.session_state['tipo_operacao_final'] = detection.contract_type
    st.session_state['home_slim_flow_operation'] = detection.contract_type


def _display_contract_label(label: object) -> str:
    text = str(label or '').strip()
    if not text or text.lower() in {'modelo universal', 'universal'}:
        return 'Modelo de destino'
    return text


def _render_model_summary(file: Any | None, df: pd.DataFrame | None, detection=None) -> None:
    if not isinstance(df, pd.DataFrame):
        return
    label = _display_contract_label(getattr(detection, 'label', 'Modelo de destino'))
    st.success(f'{label} anexado como modelo de destino.')
    st.caption(f'{_file_name(file)} · {len(df)} linha(s) · {len(df.columns)} coluna(s)')
    with st.expander('Ver colunas do modelo de destino', expanded=False):
        st.caption(_columns_caption(df))


def _classified_result(destination_file: Any, destination_df: pd.DataFrame, detection, supported_files: list[Any], ignored_files: list[Any]) -> ModelUploadResult:
    contract = detection.contract_type
    cadastro_df = destination_df if contract in {'cadastro', 'atualizacao_preco', 'universal'} else None
    estoque_df = destination_df if contract == 'estoque' else None
    cadastro_file = destination_file if cadastro_df is not None else None
    estoque_file = destination_file if estoque_df is not None else None
    return ModelUploadResult(
        cadastro_model_file=cadastro_file,
        cadastro_model_df=cadastro_df,
        estoque_model_file=estoque_file,
        estoque_model_df=estoque_df,
        model_file=destination_file,
        model_df=destination_df,
        attachments=supported_files,
        ignored_files=ignored_files,
        contract_type=contract,
        contract_label=_display_contract_label(detection.label),
        contract_confidence=float(detection.confidence),
        contract_reason=detection.reason,
    )


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
            'model_policy': 'detect_real_bling_or_universal_contract',
        },
    )

    if not supported_files:
        st.warning('Nenhuma planilha compatível encontrada. Use XLSX, XLS, CSV, XLSM ou XLSB.')
        return ModelUploadResult(attachments=[], ignored_files=ignored_files)

    with st.spinner('Lendo modelo de destino...'):
        loaded = [(file, _safe_read(file)) for file in supported_files]
        destination_file, destination_df = _pick_destination_model(loaded)

    if not _valid_model(destination_df):
        st.warning('Não encontrei colunas válidas nesse arquivo. Verifique se a planilha possui cabeçalho na primeira linha ou envie o modelo correto que será preenchido no final.')
        return ModelUploadResult(attachments=supported_files, ignored_files=ignored_files)

    detection = detect_model_contract(destination_df)
    _remember_contract_detection(detection)
    add_audit_event(
        'destination_model_selected',
        area='MODELO',
        status='OK',
        details={
            'selected_model_file': _file_audit_info(destination_file),
            'selected_df': _df_audit_info(destination_df),
            'model_policy': 'real_contract_detection',
            'contract_type': detection.contract_type,
            'contract_label': detection.label,
            'contract_confidence': detection.confidence,
            'contract_reason': detection.reason,
            'scores': detection.scores,
        },
    )
    _render_model_summary(destination_file, destination_df, detection)

    return _classified_result(destination_file, destination_df, detection, supported_files, ignored_files)


__all__ = ['MODEL_SPREADSHEET_TYPES', 'ModelUploadResult', 'render_model_upload_box']
