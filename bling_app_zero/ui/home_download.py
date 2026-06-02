from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_oauth import connection_status
from bling_app_zero.core.exporter import filename_for_operation, to_bling_csv_bytes
from bling_app_zero.core.operation_contract import (
    OP_ATUALIZACAO_PRECO,
    OP_CADASTRO,
    OP_ESTOQUE,
    OP_UNIVERSAL,
    normalize_operation,
    operation_badge,
)
from bling_app_zero.core.rules_signature import rules_signature
from bling_app_zero.core.template_download_exporter import (
    build_template_download_bytes,
    can_export_from_template,
    mime_for_template_output,
    output_name_for_template,
)
from bling_app_zero.core.validators import validate_final_df
from bling_app_zero.ui.bling_api_batch_panel import render_bling_api_batch_panel
from bling_app_zero.ui.flow_context import (
    entry_context as _entry_context,
    is_bling_api_context as _is_api_context,
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


def df_signature(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return 'empty'
    columns = '|'.join(map(str, df.columns))
    shape = f'{len(df)}x{len(df.columns)}'
    sample = pd.util.hash_pandas_object(df.head(200).astype(str), index=True).sum()
    return f'{shape}:{columns}:{sample}'


def download_label() -> str:
    return '⬇️ Baixar CSV pronto'


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
        },
    )


def download_dataframe_for_contract(df: pd.DataFrame, operation: str) -> tuple[pd.DataFrame, bool, list[str]]:
    model = model_for_operation(operation)
    adapted = adapt_dataframe_to_model_contract(df, model)
    applied = isinstance(model, pd.DataFrame) and len(model.columns) > 0
    model_columns = [str(column) for column in model.columns] if applied else []
    return adapted, applied, model_columns


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


def build_template_download(df: pd.DataFrame) -> tuple[bytes, str, str] | None:
    template = get_template_upload()
    if template is None:
        add_audit_event('template_download_original_missing_optional', area='DOWNLOAD', status='SEM_MODELO_ORIGINAL')
        return None
    template_name, template_bytes = template
    if not can_export_from_template(template_name, template_bytes):
        add_audit_event('template_download_not_supported_optional', area='DOWNLOAD', status='MODELO_NAO_SUPORTADO', details={'template_name': template_name})
        return None
    try:
        data = build_template_download_bytes(template_bytes=template_bytes, template_name=template_name, df=df)
        return data, output_name_for_template(template_name), mime_for_template_output(template_name)
    except Exception as exc:
        add_audit_event('template_download_not_ready_optional', area='DOWNLOAD', status='AGUARDANDO_AJUSTE_CONTRATO', details={'template_name': template_name, 'error': str(exc)})
        return None


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
    st.session_state[FINAL_DOWNLOAD_OPERATION_KEY] = normalize_operation(operation)
    st.session_state[FINAL_DOWNLOAD_SIGNATURE_KEY] = signature
    st.session_state[FINAL_DOWNLOAD_RULES_SIGNATURE_KEY] = rules_sig
    st.session_state[FINAL_DOWNLOAD_WIDGET_KEY] = widget_key


def _render_optional_template_download(download_df: pd.DataFrame, key: str, signature: str, rules_sig: str) -> None:
    template_export = build_template_download(download_df.copy())
    if template_export is None:
        st.caption('Opcional: modelo preenchido fiel ao arquivo original não disponível agora.')
        return
    template_bytes, template_file_name, template_mime = template_export
    st.markdown('##### Opcional · Baixar também no formato do modelo anexado')
    st.caption('Use esta opção apenas se quiser manter o formato original do modelo.')
    st.download_button(
        '⬇️ Baixar modelo preenchido',
        data=template_bytes,
        file_name=template_file_name,
        mime=template_mime,
        use_container_width=True,
        key=f'download_template_optional_{key}_{signature}_{rules_sig}',
    )


def _render_direct_bling_send(download_df: pd.DataFrame, operation: str, key: str, signature: str, rules_sig: str) -> None:
    operation = normalize_operation(operation)
    if not _is_api_context():
        return
    render_bling_api_batch_panel(download_df, operation, key, signature, rules_sig)


def _render_api_final(df_final: pd.DataFrame, operation: str, key: str = 'api_final') -> None:
    _render_direct_bling_send(df_final, operation, key, df_signature(df_final), rules_signature())


def render_download(df_final: pd.DataFrame, operation: str, key: str = 'final') -> None:
    operation = normalize_operation(operation)
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        st.warning('Nada para baixar/enviar ainda.')
        return
    download_df, contract_applied, model_columns = download_dataframe_for_contract(df_final.copy().fillna(''), operation)
    if not isinstance(download_df, pd.DataFrame) or download_df.empty:
        st.warning('Nada para baixar/enviar após aplicar o contrato da operação.')
        return
    errors = validate_final_df(download_df, operation)
    if errors:
        for error in errors:
            st.error(error)
        return
    signature = df_signature(download_df)
    rules_sig = rules_signature()
    csv_bytes = to_bling_csv_bytes(download_df, operation)
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
    _render_optional_template_download(download_df, key, signature, rules_sig)


def render_download_final(df_final: pd.DataFrame, operation: str, key: str = 'final') -> None:
    render_download(df_final, operation, key)


def download_final(df_final: pd.DataFrame, operation: str, key: str = 'final') -> None:
    render_download(df_final, operation, key)


__all__ = [
    '_render_api_final',
    'df_signature',
    'download_dataframe_for_contract',
    'download_final',
    'download_label',
    'render_download',
    'render_download_final',
]
