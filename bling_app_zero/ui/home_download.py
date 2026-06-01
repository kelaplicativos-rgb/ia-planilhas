from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender import is_direct_send_available, preview_payloads, send_dataframe_to_bling
from bling_app_zero.core.bling_oauth import connection_status
from bling_app_zero.core.exporter import filename_for_operation, to_bling_csv_bytes
from bling_app_zero.core.operation_contract import (
    OP_ATUALIZACAO_PRECO,
    OP_CADASTRO,
    OP_ESTOQUE,
    OP_UNIVERSAL,
    normalize_operation,
    operation_badge,
    operation_label,
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
    is_bling_csv_context as _is_bling_csv_context,
    is_universal_context as _is_universal_context,
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
    payload_preview = preview_payloads(download_df.copy(), operation, limit=5)
    if not payload_preview:
        st.warning('Não consegui montar prévia de payload para envio. Confira o mapeamento dos campos obrigatórios.')
        return
    ok_count = sum(1 for item in payload_preview if item.get('status') == 'OK')
    ignored_count = len(payload_preview) - ok_count
    if ok_count:
        st.success(f'Payload pronto para prévia: {ok_count} linha(s) válida(s).')
    if ignored_count:
        st.warning(f'{ignored_count} linha(s) da prévia seriam ignoradas por falta de campo obrigatório.')
    st.markdown('##### Prévia real do payload que será enviado ao Bling')
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


def _render_direct_bling_send(download_df: pd.DataFrame, operation: str, key: str, signature: str, rules_sig: str) -> None:
    operation = normalize_operation(operation)
    title = DIRECT_SEND_TEXT.get(operation, 'Envio direto ao Bling')
    st.markdown('##### Envio direto ao Bling')
    st.caption('Envia o resultado final diretamente para o Bling conectado.')
    status = connection_status()
    connected = bool(status.get('connected')) and is_direct_send_available()
    if not connected:
        st.warning('Bling não conectado. Volte ao início do caminho Bling API e conecte antes de enviar.')
        return
    if operation == OP_UNIVERSAL:
        st.warning('Envio direto exige operação definida: cadastro, estoque ou atualização de preços.')
        return
    st.success('Bling conectado. Envio direto disponível.')
    st.caption(f'Operação detectada: {operation_label(operation)} · Linhas prontas: {len(download_df)}')
    st.markdown('##### Prévia da tabela final')
    st.dataframe(download_df.head(50), use_container_width=True)
    _render_payload_preview(download_df, operation)
    button_key = f'send_direct_bling_{key}_{signature}_{rules_sig}'
    if st.button(f'🚀 {title}', use_container_width=True, key=button_key):
        progress_bar = st.progress(0, text=f'Preparando envio: 0/{len(download_df)} produto(s)')
        status_box = st.empty()

        def progress_callback(payload: dict) -> None:
            _render_send_progress(payload, progress_bar, status_box)

        with st.spinner('Realizando envio direto ao Bling...'):
            result = send_dataframe_to_bling(download_df.copy(), operation, progress_callback=progress_callback)
        _render_send_progress(
            {'stage': 'Envio concluído', 'processed': result.attempted, 'total': result.attempted, 'sent': result.sent, 'failed': result.failed, 'skipped': result.skipped, 'progress': 1.0},
            progress_bar,
            status_box,
        )
        if result.sent and not result.failed and not result.skipped:
            st.success(f'Envio concluído: {result.sent} linha(s) enviada(s) ao Bling.')
        elif result.sent:
            st.warning(f'Envio parcial: {result.sent} enviada(s), {result.failed} falha(s), {result.skipped} ignorada(s).')
        else:
            st.error(f'Nenhuma linha foi enviada. Falhas: {result.failed}. Ignoradas: {result.skipped}.')
        _render_not_found_download(download_df, tuple(getattr(result, 'not_found_indices', ())), key, signature, rules_sig)
        for error in result.errors:
            st.caption(error)


def _render_api_final(df: pd.DataFrame, operation: str, key: str) -> None:
    operation = normalize_operation(operation or st.session_state.get(FINAL_DOWNLOAD_OPERATION_KEY) or st.session_state.get('home_slim_flow_operation') or OP_UNIVERSAL)
    signature = df_signature(df)
    rules_sig = rules_signature()
    st.markdown(f'##### {operation_badge(operation)}')
    st.caption('Saída principal deste caminho: envio direto pela API. Não é necessário gerar CSV nem anexar modelo.')
    _render_direct_bling_send(df.copy().fillna(''), operation, key, signature, rules_sig)


def _render_validation_errors(errors: list[str], operation: str) -> None:
    if not errors:
        return
    st.markdown(f'##### {operation_badge(operation)} · Conferência antes do download')
    for error in errors:
        st.warning(error)


def _render_final_checklist(download_df: pd.DataFrame, operation: str, errors: list[str]) -> bool:
    st.markdown('##### Checklist final obrigatório')
    if errors:
        st.error('Download bloqueado. Corrija os itens abaixo antes de baixar o CSV final.')
        _render_validation_errors(errors, operation)
        st.caption('Volte para Mapeamento ou Revisão final, ajuste os campos e gere a prévia final novamente.')
        add_audit_event('download_blocked_by_final_checklist', area='DOWNLOAD', status='BLOQUEADO', details={'operation': operation, 'errors': errors[:20], 'row_count': len(download_df), 'home_entry_context': _entry_context()})
        return False
    st.success('Checklist aprovado: arquivo final validado para download.')
    st.caption('CSV com separador ; e codificação UTF-8-SIG será gerado a partir da base validada.')
    return True


def _missing_contract_message() -> str:
    if _is_universal_context():
        return 'Reenvie o modelo de destino antes de baixar.'
    return 'Reenvie a planilha modelo antes de baixar.'


def _render_csv_final(df: pd.DataFrame, operation: str, key: str) -> None:
    operation = normalize_operation(operation or st.session_state.get(FINAL_DOWNLOAD_OPERATION_KEY) or OP_UNIVERSAL)
    operation_title = operation_label(operation)
    st.markdown(f'##### {operation_badge(operation)}')
    st.caption(f'Arquivo final: {operation_title}. A saída principal é CSV com separador ; e UTF-8-SIG.')
    if st.session_state.pop('final_download_done', False):
        st.success('✅ Download concluído. Os dados continuam preservados nesta tela.')
    download_df, contract_applied, model_columns = download_dataframe_for_contract(df, operation)
    if not contract_applied:
        st.warning(_missing_contract_message())
        add_audit_event('download_contract_missing', area='DOWNLOAD', status='AGUARDANDO_MODELO', details={'home_entry_context': _entry_context()})
        return
    st.success('Modelo de destino aplicado. O arquivo final será gerado respeitando as colunas do modelo.')
    st.caption('Colunas do modelo que serão preenchidas: ' + ', '.join(model_columns))
    validation_errors = validate_final_df(download_df, operation)
    if not _render_final_checklist(download_df, operation, validation_errors):
        return
    signature = df_signature(download_df)
    rules_sig = rules_signature()
    csv_bytes = to_bling_csv_bytes(download_df.copy(), operation=operation, contract_columns=model_columns)
    csv_file_name = filename_for_operation(operation)
    widget_key = f'download_csv_{_entry_context() or "fluxo"}_{key}_{signature}_{rules_sig}'
    save_download_snapshot(download_df=download_df, file_bytes=csv_bytes, file_name=csv_file_name, mime='text/csv', operation=operation, signature=signature, rules_sig=rules_sig, widget_key=widget_key)
    label = '⬇️ Baixar CSV Bling pronto para importar' if _is_bling_csv_context() else '⬇️ Baixar arquivo final'
    st.success('Arquivo final pronto.')
    st.download_button(label, data=st.session_state.get(FINAL_DOWNLOAD_FILE_BYTES_KEY, csv_bytes), file_name=str(st.session_state.get(FINAL_DOWNLOAD_FILE_NAME_KEY) or csv_file_name), mime=str(st.session_state.get(FINAL_DOWNLOAD_MIME_KEY) or 'text/csv'), use_container_width=True, key=widget_key, on_click=after_final_download, args=(operation, signature, rules_sig))
    _render_optional_template_download(download_df, key, signature, rules_sig)

    status = connection_status()
    if bool(status.get('connected')) and is_direct_send_available():
        st.divider()
        st.info('Bling conectado detectado. Você também pode enviar esta mesma tabela final direto pela API, sem depender do CSV.')
        _render_direct_bling_send(download_df.copy().fillna(''), operation, f'{key}_csv_fallback', signature, rules_sig)
    else:
        st.caption('Para enviar direto ao Bling nesta tela, conecte o Bling no caminho Bling API.')


def download_final(df: pd.DataFrame, operation: str, key: str) -> None:
    if df is None or df.empty:
        snapshot = st.session_state.get(FINAL_DOWNLOAD_DF_SNAPSHOT_KEY)
        if isinstance(snapshot, pd.DataFrame) and not snapshot.empty:
            df = snapshot.copy().fillna('')
        else:
            st.warning('Ainda não há dados finais para concluir.')
            return
    if _is_api_context():
        _render_api_final(df, operation, key)
        return
    _render_csv_final(df, operation, key)


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
