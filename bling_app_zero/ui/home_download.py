from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender_safe import is_direct_send_available, preview_payloads, send_dataframe_to_bling
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
DIRECT_SEND_RESULT_STATE_KEY = 'bling_direct_send_last_result_v3'
PRESERVED_DOWNLOAD_OPERATIONS = {OP_CADASTRO, OP_ESTOQUE, OP_UNIVERSAL, OP_ATUALIZACAO_PRECO}

DIRECT_SEND_TEXT = {
    OP_CADASTRO: 'Cadastrar produtos no Bling',
    OP_ESTOQUE: 'Atualizar estoque no Bling',
    OP_ATUALIZACAO_PRECO: 'Atualizar preços no Bling',
    OP_UNIVERSAL: 'Envio direto ao Bling',
}


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


def _render_payload_preview(download_df: pd.DataFrame, operation: str) -> None:
    preview_limit = 5
    preview_source = download_df.head(preview_limit).copy().fillna('')
    add_audit_event(
        'bling_payload_preview_limited_on_ui',
        area='BLING_ENVIO',
        status='OK',
        details={
            'source_rows': len(download_df),
            'preview_rows': len(preview_source),
            'responsible_file': 'bling_app_zero/ui/home_download.py',
        },
    )
    payload_preview = preview_payloads(preview_source, operation, limit=preview_limit)
    if not payload_preview:
        st.warning('Não consegui montar prévia de payload para envio. Confira os campos obrigatórios.')
        return
    ok_count = sum(1 for item in payload_preview if item.get('status') == 'OK')
    ignored_count = len(payload_preview) - ok_count
    if ok_count:
        st.success(f'Payload pronto para prévia: {ok_count} linha(s) válida(s).')
    if ignored_count:
        st.warning(f'{ignored_count} linha(s) da prévia seriam ignoradas por falta de campo obrigatório.')
    st.markdown('##### Prévia real do payload que será enviado ao Bling')
    st.caption('Prévia limitada a 5 linhas para não travar o celular. O envio completo só roda depois do botão.')
    for index, item in enumerate(payload_preview, start=1):
        st.markdown(f'**Linha {index} · {item.get("status", "")}**')
        motivo = str(item.get('motivo') or '').strip()
        if motivo:
            st.caption(motivo)
        st.json(item.get('payload') or {})


def _render_not_found_download(download_df: pd.DataFrame, not_found_indices: tuple[int, ...], key: str, signature: str, rules_sig: str) -> None:
    valid_indices = [idx for idx in not_found_indices if idx in download_df.index]
    if not valid_indices:
        return
    missing_df = download_df.loc[valid_indices].copy().fillna('')
    if missing_df.empty:
        return
    missing_df.insert(0, 'motivo_bling', 'Produto não encontrado no Bling durante atualização de estoque/preço')
    missing_df.insert(1, 'acao_recomendada', 'Cadastrar este produto no Bling e depois refazer o fluxo de atualização de estoque')
    csv_bytes = missing_df.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
    st.warning(f'{len(missing_df)} produto(s) não encontrado(s) no Bling. Baixe esta lista para cadastro/conferência.')
    st.download_button(
        '⬇️ Baixar produtos não encontrados para cadastro',
        data=csv_bytes,
        file_name='produtos_nao_encontrados_no_bling.csv',
        mime='text/csv',
        use_container_width=True,
        key=f'download_not_found_bling_{key}_{signature}_{rules_sig}_{len(missing_df)}',
    )
    st.markdown('##### Prévia dos produtos não encontrados')
    st.dataframe(missing_df.head(100), use_container_width=True)
    add_audit_event(
        'bling_direct_not_found_download_ready',
        area='BLING_ENVIO',
        status='OK',
        details={'not_found_count': len(missing_df), 'responsible_file': 'bling_app_zero/ui/home_download.py'},
    )


def _render_send_progress(payload: dict, progress_bar, status_box) -> None:
    total = int(payload.get('total') or 0)
    processed = int(payload.get('processed') or 0)
    sent = int(payload.get('sent') or 0)
    failed = int(payload.get('failed') or 0)
    skipped = int(payload.get('skipped') or 0)
    ratio = float(payload.get('progress') or 0.0)
    percent = max(0, min(100, int(round(ratio * 100))))
    stage = str(payload.get('stage') or 'Enviando ao Bling')
    text = f'{stage}: {processed}/{total} produto(s) · enviados {sent} · falhas {failed} · ignorados {skipped}'
    try:
        progress_bar.progress(percent, text=text)
    except Exception:
        pass
    try:
        status_box.caption(text)
    except Exception:
        pass


def _result_identity(operation: str, key: str, signature: str, rules_sig: str) -> str:
    return f'{normalize_operation(operation)}::{key}::{signature}::{rules_sig}'


def _store_direct_send_result(result, operation: str, key: str, signature: str, rules_sig: str) -> None:
    st.session_state[DIRECT_SEND_RESULT_STATE_KEY] = {
        'identity': _result_identity(operation, key, signature, rules_sig),
        'operation': normalize_operation(operation),
        'attempted': int(result.attempted),
        'sent': int(result.sent),
        'failed': int(result.failed),
        'skipped': int(result.skipped),
        'errors': list(result.errors or ()),
        'not_found_indices': list(result.not_found_indices or ()),
    }


def _render_persisted_direct_send_result(download_df: pd.DataFrame, operation: str, key: str, signature: str, rules_sig: str) -> None:
    data = st.session_state.get(DIRECT_SEND_RESULT_STATE_KEY)
    if not isinstance(data, dict):
        return
    if data.get('identity') != _result_identity(operation, key, signature, rules_sig):
        return

    attempted = int(data.get('attempted') or 0)
    sent = int(data.get('sent') or 0)
    failed = int(data.get('failed') or 0)
    skipped = int(data.get('skipped') or 0)
    errors = [str(error) for error in list(data.get('errors') or [])]
    not_found_indices = tuple(int(item) for item in list(data.get('not_found_indices') or []) if str(item).lstrip('-').isdigit())

    st.markdown('### Resultado do envio ao Bling')
    if attempted == 0:
        st.error('Envio não iniciado: nenhum produto foi processado.')
    elif failed == 0 and skipped == 0:
        st.success(f'Envio concluído com sucesso: {sent}/{attempted} produto(s) enviado(s) ao Bling.')
    elif sent > 0:
        st.warning(f'Envio parcialmente concluído: {sent}/{attempted} enviado(s), {failed} falha(s), {skipped} ignorado(s).')
    else:
        st.error(f'Envio não concluído: 0/{attempted} enviado(s), {failed} falha(s), {skipped} ignorado(s).')

    cols = st.columns(4)
    cols[0].metric('Processados', attempted)
    cols[1].metric('Enviados', sent)
    cols[2].metric('Falhas', failed)
    cols[3].metric('Ignorados', skipped)

    for error in errors[:8]:
        st.error(error)
    _render_not_found_download(download_df, not_found_indices, key, signature, rules_sig)

    add_audit_event(
        'bling_direct_send_result_visible_persisted',
        area='BLING_ENVIO',
        status='OK' if failed == 0 and skipped == 0 else 'PARCIAL',
        details={
            'operation': operation,
            'attempted': attempted,
            'sent': sent,
            'failed': failed,
            'skipped': skipped,
            'responsible_file': 'bling_app_zero/ui/home_download.py',
        },
    )


def _render_direct_bling_send(download_df: pd.DataFrame, operation: str, key: str, signature: str, rules_sig: str) -> None:
    operation = normalize_operation(operation)
    if not _is_api_context():
        return
    st.markdown('### Envio direto ao Bling')
    status = connection_status()
    if not status.get('connected'):
        st.warning('Bling não conectado. Conecte o Bling no início do fluxo para enviar direto pela API.')
        return
    if not is_direct_send_available():
        st.warning('Token do Bling indisponível. Reconecte o Bling e tente novamente.')
        return
    _render_payload_preview(download_df, operation)
    _render_persisted_direct_send_result(download_df, operation, key, signature, rules_sig)
    button_text = DIRECT_SEND_TEXT.get(operation, 'Enviar ao Bling')
    if st.button(button_text, use_container_width=True, key=f'direct_send_bling_{key}_{signature}_{rules_sig}'):
        add_audit_event('bling_direct_send_clicked', area='BLING_ENVIO', status='INICIADO', details={'operation': operation, 'rows': len(download_df), 'responsible_file': 'bling_app_zero/ui/home_download.py'})
        progress_bar = st.progress(0, text='Enviando ao Bling...')
        status_box = st.empty()
        result = send_dataframe_to_bling(download_df, operation, progress_callback=lambda payload: _render_send_progress(payload, progress_bar, status_box))
        _store_direct_send_result(result, operation, key, signature, rules_sig)
        try:
            progress_bar.empty()
            status_box.empty()
        except Exception:
            pass
        _render_persisted_direct_send_result(download_df, operation, key, signature, rules_sig)
        add_audit_event('bling_direct_send_result_rendered', area='BLING_ENVIO', status='OK' if result.failed == 0 else 'PARCIAL', details={'operation': operation, 'attempted': result.attempted, 'sent': result.sent, 'failed': result.failed, 'skipped': result.skipped, 'not_found_count': len(result.not_found_indices), 'responsible_file': 'bling_app_zero/ui/home_download.py'})


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
