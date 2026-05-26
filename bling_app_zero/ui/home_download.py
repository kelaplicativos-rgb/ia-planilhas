from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.rules_signature import rules_signature
from bling_app_zero.core.template_download_exporter import (
    build_template_download_bytes,
    can_export_from_template,
    mime_for_template_output,
    output_name_for_template,
)
from bling_app_zero.core.validators import validate_final_df
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

OPERATION_LABELS = {
    'cadastro': 'Modelo final preenchido',
    'estoque': 'Modelo final preenchido',
    'universal': 'Modelo final preenchido',
}


def df_signature(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return 'empty'
    columns = '|'.join(map(str, df.columns))
    shape = f'{len(df)}x{len(df.columns)}'
    sample = pd.util.hash_pandas_object(df.head(200).astype(str), index=True).sum()
    return f'{shape}:{columns}:{sample}'


def operation_label(operation: str) -> str:
    op = str(operation or '').strip().lower()
    if op in {'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}:
        op = 'universal'
    return OPERATION_LABELS.get(op, 'Modelo final preenchido')


def operation_badge(operation: str) -> str:
    _ = operation
    return '📄 MODELO FINAL'


def download_label() -> str:
    return '⬇️ Baixar modelo preenchido'


def preserve_flow_after_download(operation: str) -> None:
    op = str(operation or '').strip().lower()
    preserved_operation = op if op in {'cadastro', 'estoque', 'universal'} else 'universal'
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
    except Exception:
        pass


def after_final_download(operation: str, signature: str, rules_sig: str) -> None:
    preserve_flow_after_download(operation)
    st.session_state['final_download_cache_cleaned'] = False
    st.session_state['final_download_done'] = True
    st.session_state[FINAL_DOWNLOAD_OPERATION_KEY] = operation
    add_audit_event(
        'final_download_completed_navigation_preserved',
        area='DOWNLOAD',
        details={'operation': operation, 'signature': signature, 'rules_signature': rules_sig, 'download_state_preserved': True},
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
        st.warning('Reenvie a planilha modelo para gerar o arquivo final fiel ao layout anexado.')
        add_audit_event('template_download_original_missing', area='DOWNLOAD', status='AGUARDANDO_MODELO')
        return None
    template_name, template_bytes = template
    if not can_export_from_template(template_name, template_bytes):
        st.warning('Este formato ainda não permite download 100% fiel. Use CSV, XLSX ou XLSM como modelo de destino.')
        add_audit_event('template_download_not_supported', area='DOWNLOAD', status='AGUARDANDO_MODELO_VALIDO', details={'template_name': template_name})
        return None
    try:
        data = build_template_download_bytes(template_bytes=template_bytes, template_name=template_name, df=df)
        return data, output_name_for_template(template_name), mime_for_template_output(template_name)
    except Exception as exc:
        add_audit_event('template_download_not_ready', area='DOWNLOAD', status='AGUARDANDO_AJUSTE_CONTRATO', details={'template_name': template_name, 'error': str(exc)})
        st.warning('A planilha modelo ainda não está pronta para download final fiel ao layout anexado.')
        st.caption(str(exc))
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
    st.session_state[FINAL_DOWNLOAD_OPERATION_KEY] = operation
    st.session_state[FINAL_DOWNLOAD_SIGNATURE_KEY] = signature
    st.session_state[FINAL_DOWNLOAD_RULES_SIGNATURE_KEY] = rules_sig
    st.session_state[FINAL_DOWNLOAD_WIDGET_KEY] = widget_key


def download_final(df: pd.DataFrame, operation: str, key: str) -> None:
    if df is None or df.empty:
        snapshot = st.session_state.get(FINAL_DOWNLOAD_DF_SNAPSHOT_KEY)
        if isinstance(snapshot, pd.DataFrame) and not snapshot.empty:
            df = snapshot.copy().fillna('')
        else:
            st.warning('Ainda não há dados finais para baixar.')
            return

    operation = str(operation or st.session_state.get(FINAL_DOWNLOAD_OPERATION_KEY) or 'universal').strip().lower()
    if operation in {'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}:
        operation = 'universal'

    operation_title = operation_label(operation)
    st.markdown(f'##### {operation_badge(operation)}')
    st.caption(f'Arquivo final: {operation_title}. A saída respeita o modelo anexado como contrato absoluto.')

    if st.session_state.pop('final_download_done', False):
        st.success('✅ Download concluído. Os dados continuam preservados nesta tela para você continuar usando o sistema.')

    download_df, contract_applied, model_columns = download_dataframe_for_contract(df, operation)
    if not contract_applied:
        st.warning('Reenvie a planilha modelo antes de baixar.')
        add_audit_event('download_contract_missing', area='DOWNLOAD', status='AGUARDANDO_MODELO')
        return

    st.success('Modelo de destino aplicado. O arquivo final será gerado fiel ao modelo anexado.')
    with st.expander('Colunas do modelo que serão preenchidas', expanded=False):
        st.caption(', '.join(model_columns))

    errors = validate_final_df(download_df, operation)
    if errors:
        try:
            with st.expander(f'{operation_badge(operation)} · Conferência antes do download', expanded=True):
                for error in errors:
                    st.warning(error)
        except StreamlitAPIException as exc:
            if 'Expanders may not be nested' not in str(exc):
                raise
            st.markdown(f'##### {operation_badge(operation)} · Conferência antes do download')
            for error in errors:
                st.warning(error)

    signature = df_signature(download_df)
    rules_sig = rules_signature()
    template_export = build_template_download(download_df.copy())
    if template_export is None:
        return

    template_bytes, template_file_name, template_mime = template_export
    widget_key = f'download_template_{key}_{signature}_{rules_sig}'
    save_download_snapshot(
        download_df=download_df,
        file_bytes=template_bytes,
        file_name=template_file_name,
        mime=template_mime,
        operation=operation,
        signature=signature,
        rules_sig=rules_sig,
        widget_key=widget_key,
    )

    st.success('Modelo preenchido pronto para download.')
    st.download_button(
        download_label(),
        data=st.session_state.get(FINAL_DOWNLOAD_FILE_BYTES_KEY, template_bytes),
        file_name=str(st.session_state.get(FINAL_DOWNLOAD_FILE_NAME_KEY) or template_file_name),
        mime=str(st.session_state.get(FINAL_DOWNLOAD_MIME_KEY) or template_mime),
        use_container_width=True,
        key=widget_key,
        on_click=after_final_download,
        args=(operation, signature, rules_sig),
    )


__all__ = [
    'DESTINATION_MODEL_UPLOAD_BYTES_KEY',
    'DESTINATION_MODEL_UPLOAD_NAME_KEY',
    'DESTINATION_MODEL_UPLOAD_OBJECT_KEY',
    'FINAL_DOWNLOAD_DF_SNAPSHOT_KEY',
    'FINAL_DOWNLOAD_FILE_BYTES_KEY',
    'FINAL_DOWNLOAD_FILE_NAME_KEY',
    'FINAL_DOWNLOAD_MIME_KEY',
    'FINAL_DOWNLOAD_OPERATION_KEY',
    'FINAL_DOWNLOAD_RULES_SIGNATURE_KEY',
    'FINAL_DOWNLOAD_SIGNATURE_KEY',
    'FINAL_DOWNLOAD_WIDGET_KEY',
    'df_signature',
    'download_final',
]
