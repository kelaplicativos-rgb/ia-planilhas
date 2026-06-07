from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.exporter import enforce_export_contract, filename_for_operation, to_bling_csv_bytes
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.flow_spine_output import output_diagnostics, output_is_api, output_operation
from bling_app_zero.core.operation_contract import (
    OP_ATUALIZACAO_PRECO,
    OP_CADASTRO,
    OP_ESTOQUE,
    OP_UNIVERSAL,
    normalize_operation,
    operation_badge,
)
from bling_app_zero.core.rules_signature import rules_signature
from bling_app_zero.core.text import normalize_key
from bling_app_zero.core.validators import validate_final_df
from bling_app_zero.ui.bling_api_batch_panel import render_bling_api_batch_panel
from bling_app_zero.ui.flow_context import (
    entry_context as _entry_context,
    is_bling_api_context as _legacy_is_api_context,
)
from bling_app_zero.universal.contract_adapter import adapt_dataframe_to_model_contract, model_for_operation

DESTINATION_MODEL_UPLOAD_OBJECT_KEY = 'destination_model_upload_object'
DESTINATION_MODEL_UPLOAD_NAME_KEY = 'destination_model_upload_name'
DESTINATION_MODEL_UPLOAD_BYTES_KEY = 'destination_model_upload_bytes'
FINAL_DOWNLOAD_DF_SNAPSHOT_KEY = 'final_download_df_snapshot'
FINAL_DOWNLOAD_FILE_BYTES_KEY = 'final_download_file_bytes'
FINAL_DOWNLOAD_FILE_NAME_KEY = 'final_download_file_name'
FINAL_DOWNLOAD_MIME_KEY = 'final_download_mime'
FINAL_DOWNLOAD_SIGNATURE_KEY = 'final_download_signature'
FINAL_DOWNLOAD_RULES_SIGNATURE_KEY = 'final_download_rules_signature'
FINAL_DOWNLOAD_OPERATION_KEY = 'final_download_operation'
FINAL_DOWNLOAD_WIDGET_KEY = 'final_download_widget_key'
PRESERVED_DOWNLOAD_OPERATIONS = {OP_CADASTRO, OP_ESTOQUE, OP_UNIVERSAL, OP_ATUALIZACAO_PRECO}
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_download.py'

CADASTRO_NAME_TERMS = ('nome', 'descricao', 'descrição', 'produto', 'titulo', 'título')
CADASTRO_PRICE_TERMS = ('preco', 'preço', 'valor', 'unitario', 'unitário', 'venda')
ESTOQUE_QTY_TERMS = ('quantidade', 'qtd', 'saldo', 'estoque', 'balanco', 'balanço')
ESTOQUE_DEPOSIT_TERMS = ('deposito', 'depósito')
ESTOQUE_CODE_TERMS = ('codigo', 'código', 'sku', 'referencia', 'referência', 'id')
STOCK_ONLY_STRICT_COLUMNS = {'quantidade', 'id', 'codigo', 'gtin', 'deposito'}


class _NamedBytesIO(BytesIO):
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


def df_signature(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return 'empty'
    columns = '|'.join(map(str, df.columns))
    shape = f'{len(df)}x{len(df.columns)}'
    sample = pd.util.hash_pandas_object(df.head(200).astype(str), index=True).sum()
    return f'{shape}:{columns}:{sample}'


def download_label() -> str:
    return '⬇️ Baixar arquivo final para o Bling'


def _is_api_context() -> bool:
    try:
        return output_is_api()
    except Exception:
        return _legacy_is_api_context()


def _spine_operation_or(operation: str) -> str:
    try:
        op = normalize_operation(output_operation())
        if op:
            return op
    except Exception:
        pass
    return normalize_operation(operation)


def _normalized_columns(df: pd.DataFrame) -> list[str]:
    if not isinstance(df, pd.DataFrame):
        return []
    return [normalize_key(column) for column in df.columns]


def _has_term(columns: list[str], terms: tuple[str, ...]) -> bool:
    normalized_terms = [normalize_key(term) for term in terms]
    return any(any(term in column for term in normalized_terms) for column in columns)


def _looks_like_stock_contract(df: pd.DataFrame) -> bool:
    columns = set(_normalized_columns(df))
    if not columns:
        return False
    strict_stock = columns.issubset(STOCK_ONLY_STRICT_COLUMNS) and bool(columns.intersection({'quantidade', 'saldo', 'estoque', 'deposito'}))
    stock_terms = _has_term(list(columns), ESTOQUE_QTY_TERMS) and (_has_term(list(columns), ESTOQUE_DEPOSIT_TERMS) or _has_term(list(columns), ESTOQUE_CODE_TERMS))
    cadastro_terms = _has_term(list(columns), CADASTRO_NAME_TERMS) or _has_term(list(columns), CADASTRO_PRICE_TERMS)
    return bool(strict_stock or (stock_terms and not cadastro_terms))


def _looks_like_cadastro_contract(df: pd.DataFrame) -> bool:
    columns = _normalized_columns(df)
    return _has_term(columns, CADASTRO_NAME_TERMS) and _has_term(columns, CADASTRO_PRICE_TERMS)


def _operation_contract_mismatch_error(raw_df: pd.DataFrame, download_df: pd.DataFrame, operation: str) -> str:
    op = normalize_operation(operation)
    raw_columns = list(map(str, raw_df.columns)) if isinstance(raw_df, pd.DataFrame) else []
    download_columns = list(map(str, download_df.columns)) if isinstance(download_df, pd.DataFrame) else []

    if op == OP_CADASTRO:
        if _looks_like_stock_contract(raw_df) or _looks_like_stock_contract(download_df) or not _looks_like_cadastro_contract(download_df):
            add_audit_event(
                'final_download_contract_mismatch_blocked',
                area='DOWNLOAD',
                status='BLOQUEADO',
                details={
                    'operation': op,
                    'raw_columns': raw_columns,
                    'download_columns': download_columns,
                    'raw_looks_stock': _looks_like_stock_contract(raw_df),
                    'download_looks_stock': _looks_like_stock_contract(download_df),
                    'download_looks_cadastro': _looks_like_cadastro_contract(download_df),
                    'flow_spine': output_diagnostics(),
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return (
                'Operação bloqueada por segurança: você está em Cadastro de produtos, mas a tabela final parece estoque '
                'ou não contém campos reais de cadastro como Nome/Descrição e Preço. Volte ao preview final e gere novamente o arquivo de Cadastro.'
            )

    if op == OP_ESTOQUE:
        if _looks_like_cadastro_contract(download_df) and not _looks_like_stock_contract(download_df):
            add_audit_event(
                'final_download_contract_mismatch_blocked',
                area='DOWNLOAD',
                status='BLOQUEADO',
                details={
                    'operation': op,
                    'raw_columns': raw_columns,
                    'download_columns': download_columns,
                    'download_looks_cadastro': _looks_like_cadastro_contract(download_df),
                    'download_looks_stock': _looks_like_stock_contract(download_df),
                    'flow_spine': output_diagnostics(),
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return (
                'Operação bloqueada por segurança: você está em Atualização de estoque, mas a tabela final parece Cadastro. '
                'Volte e selecione a operação correta antes de baixar/enviar.'
            )

    return ''


def preserve_flow_after_download(operation: str) -> None:
    op = normalize_operation(operation)
    preserved_operation = op if op in PRESERVED_DOWNLOAD_OPERATIONS else OP_UNIVERSAL
    st.session_state['home_active_operation_v2'] = 'wizard_cadastro_estoque'
    st.session_state['home_slim_flow_operation'] = preserved_operation
    st.session_state['operacao_final'] = preserved_operation
    st.session_state['tipo_operacao_final'] = preserved_operation
    st.session_state['home_detected_operation'] = preserved_operation
    st.session_state['bling_wizard_step'] = 'download'
    st.session_state['home_single_page_flow_active'] = True
    try:
        st.query_params['operation_v2'] = 'wizard_cadastro_estoque'
        st.query_params['step'] = 'download'
        st.query_params.pop('operation', None)
    except Exception:
        pass


def after_final_download(operation: str, signature: str, rules_sig: str) -> None:
    preserve_flow_after_download(operation)
    st.session_state['final_download_cache_cleaned'] = False
    st.session_state['final_download_done'] = True
    st.session_state[FINAL_DOWNLOAD_OPERATION_KEY] = normalize_operation(operation)
    add_audit_event(
        'final_csv_download_completed_navigation_preserved',
        area='DOWNLOAD',
        details={
            'operation': operation,
            'signature': signature,
            'rules_signature': rules_sig,
            'download_state_preserved': True,
            'home_entry_context': _entry_context(),
            'flow_spine': output_diagnostics(),
        },
    )


def get_template_upload() -> tuple[str, bytes] | None:
    name = str(st.session_state.get(DESTINATION_MODEL_UPLOAD_NAME_KEY) or '').strip()
    data = st.session_state.get(DESTINATION_MODEL_UPLOAD_BYTES_KEY)
    if name and isinstance(data, (bytes, bytearray)) and data:
        return name, bytes(data)
    uploaded = st.session_state.get(DESTINATION_MODEL_UPLOAD_OBJECT_KEY)
    if uploaded is None:
        return None
    name = str(getattr(uploaded, 'name', '') or name).strip()
    try:
        data = uploaded.getvalue()
    except Exception:
        data = None
    if not name or not data:
        return None
    data_bytes = bytes(data)
    st.session_state[DESTINATION_MODEL_UPLOAD_NAME_KEY] = name
    st.session_state[DESTINATION_MODEL_UPLOAD_BYTES_KEY] = data_bytes
    return name, data_bytes


def _uploaded_model_contract_columns() -> list[str]:
    template = get_template_upload()
    if template is None:
        return []
    template_name, template_bytes = template
    try:
        model_df = read_uploaded_file(_NamedBytesIO(template_bytes, template_name))
    except Exception as exc:
        add_audit_event(
            'uploaded_model_contract_read_failed',
            area='DOWNLOAD',
            status='IGNORADO',
            details={'template_name': template_name, 'error': str(exc), 'responsible_file': RESPONSIBLE_FILE},
        )
        return []
    if not isinstance(model_df, pd.DataFrame) or len(model_df.columns) <= 0:
        return []
    return [str(column).replace('\ufeff', '').replace('\r', ' ').replace('\n', ' ').strip() for column in model_df.columns]


def download_dataframe_for_contract(df: pd.DataFrame, operation: str) -> tuple[pd.DataFrame, bool, list[str]]:
    uploaded_columns = _uploaded_model_contract_columns()
    if uploaded_columns:
        adapted = enforce_export_contract(df, uploaded_columns)
        add_audit_event(
            'final_download_uses_uploaded_model_contract',
            area='DOWNLOAD',
            status='OK',
            details={
                'operation': normalize_operation(operation),
                'columns': len(uploaded_columns),
                'source': 'uploaded_model',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return adapted, True, uploaded_columns

    model = model_for_operation(operation)
    adapted = adapt_dataframe_to_model_contract(df, model)
    applied = isinstance(model, pd.DataFrame) and len(model.columns) > 0
    model_columns = [str(column) for column in model.columns] if applied else []
    return adapted, applied, model_columns


def save_download_snapshot(
    *,
    download_df: pd.DataFrame,
    file_bytes: bytes,
    file_name: str,
    mime: str,
    operation: str,
    signature: str,
    rules_sig: str,
    widget_key: str,
) -> None:
    st.session_state[FINAL_DOWNLOAD_DF_SNAPSHOT_KEY] = download_df.copy().fillna('')
    st.session_state[FINAL_DOWNLOAD_FILE_BYTES_KEY] = bytes(file_bytes)
    st.session_state[FINAL_DOWNLOAD_FILE_NAME_KEY] = file_name
    st.session_state[FINAL_DOWNLOAD_MIME_KEY] = mime
    st.session_state[FINAL_DOWNLOAD_RULES_SIGNATURE_KEY] = rules_sig
    st.session_state[FINAL_DOWNLOAD_WIDGET_KEY] = widget_key
    st.session_state['flow_spine_sender_operation'] = normalize_operation(operation)
    st.session_state['flow_spine_sender_destination'] = 'api_bling' if _is_api_context() else 'csv_download'


def _render_direct_bling_send(download_df: pd.DataFrame, operation: str, key: str, signature: str, rules_sig: str) -> None:
    operation = _spine_operation_or(operation)
    if not _is_api_context():
        add_audit_event('final_api_send_skipped_by_flow_spine', area='DOWNLOAD', status='PULADO', details={'operation': operation, 'flow_spine': output_diagnostics(), 'responsible_file': RESPONSIBLE_FILE})
        return
    st.session_state['flow_spine_sender_operation'] = operation
    st.session_state['flow_spine_sender_destination'] = 'api_bling'
    add_audit_event('final_api_send_rendered_by_flow_spine', area='DOWNLOAD', status='OK', details={'operation': operation, 'rows': len(download_df), 'columns': len(download_df.columns), 'flow_spine': output_diagnostics(), 'responsible_file': RESPONSIBLE_FILE})
    render_bling_api_batch_panel(download_df, operation, key, signature, rules_sig)


def _render_api_final(df_final: pd.DataFrame, operation: str, key: str = 'api_final') -> None:
    operation = _spine_operation_or(operation)
    _render_direct_bling_send(df_final, operation, key, df_signature(df_final), rules_signature())


def render_download(df_final: pd.DataFrame, operation: str, key: str = 'final') -> None:
    operation = _spine_operation_or(operation)
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        st.warning('Nada para baixar/enviar ainda.')
        return

    raw_df = df_final.copy().fillna('')
    download_df, contract_applied, model_columns = download_dataframe_for_contract(raw_df.copy(), operation)
    if not isinstance(download_df, pd.DataFrame) or download_df.empty:
        st.warning('Nada para baixar/enviar após aplicar o contrato da operação.')
        return

    mismatch_error = _operation_contract_mismatch_error(raw_df, download_df, operation)
    if mismatch_error:
        st.error(mismatch_error)
        st.warning('Envio e download foram bloqueados para evitar cadastro incorreto no Bling.')
        return

    errors = validate_final_df(download_df, operation)
    if errors:
        for error in errors:
            st.error(error)
        return

    signature = df_signature(download_df)
    rules_sig = rules_signature()
    try:
        csv_bytes = to_bling_csv_bytes(download_df, operation, contract_columns=model_columns if contract_applied else None)
    except Exception as exc:
        st.error('CSV final bloqueado: o arquivo perderia o contrato de colunas aceito pelo Bling.')
        st.warning(str(exc))
        return
    file_name = filename_for_operation(operation)
    save_download_snapshot(download_df=download_df, file_bytes=csv_bytes, file_name=file_name, mime='text/csv; charset=utf-8', operation=operation, signature=signature, rules_sig=rules_sig, widget_key=key)
    if contract_applied:
        st.success(f'Contrato aplicado: {operation_badge(operation)} · {len(model_columns)} coluna(s).')
    if _is_api_context():
        _render_direct_bling_send(download_df, operation, key, signature, rules_sig)
        st.caption('Backup opcional em CSV')
        st.download_button(
            download_label(),
            data=csv_bytes,
            file_name=file_name,
            mime='text/csv; charset=utf-8',
            use_container_width=True,
            key=f'download_csv_backup_{key}_{signature}_{rules_sig}',
        )
        return
    st.download_button(download_label(), data=csv_bytes, file_name=file_name, mime='text/csv; charset=utf-8', use_container_width=True, key=f'download_csv_{key}_{signature}_{rules_sig}', on_click=after_final_download, args=(operation, signature, rules_sig))


def download_final(df_final: pd.DataFrame, operation: str, key: str = 'final') -> None:
    render_download(df_final, operation, key)


__all__ = ['df_signature', 'download_final', 'download_label', 'render_download']
