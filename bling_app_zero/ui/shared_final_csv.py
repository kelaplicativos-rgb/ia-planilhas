from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_oauth import build_authorization_url, connection_status
from bling_app_zero.core.final_csv_exporter import contract_columns_from_model
from bling_app_zero.core.final_output_engine import apply_text_rules, build_final_dataframe, build_final_output, build_final_output_report
from bling_app_zero.core.modelo_compactado_universal import resolver_modelo
from bling_app_zero.core.oauth_return_snapshot import prepare_download_oauth_return
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, OP_UNIVERSAL, operation_label
from bling_app_zero.core.template_download_exporter import (
    build_template_download_bytes,
    can_export_from_template,
    mime_for_template_output,
    output_name_for_template,
)
from bling_app_zero.ui.bling_api_batch_panel import render_bling_api_batch_panel
from bling_app_zero.ui.home_bling_api_flow import render_new_tab_connect_button

RESPONSIBLE_FILE = 'bling_app_zero/ui/shared_final_csv.py'
FINAL_OUTPUT_STATE_KEY = 'neutral_final_output_state_v1'
FINAL_OUTPUT_REPORT_KEY = 'neutral_final_output_report_v1'
MODEL_TEMPLATE_UPLOAD_KEYS = (
    'mapeiaai_universal_model_upload',
    'mapeiaai_shared_model_upload',
    'home_modelo_universal_upload',
)
MODEL_TEMPLATE_NAME_KEYS = (
    'mapeiaai_universal_model_file_name',
    'mapeiaai_model_template_name',
)
MODEL_TEMPLATE_BYTES_KEYS = (
    'mapeiaai_universal_model_file_bytes',
    'mapeiaai_model_template_bytes',
)
SUPPORTED_PRESERVE_SUFFIXES = {'.csv', '.xlsx', '.xlsm'}
EXCEL_LIKE_SUFFIXES = {'.xlsx', '.xlsm', '.xls', '.xlsb'}
DOWNLOAD_READY_KEY = 'mapeiaai_final_download_ready'
FINAL_API_PANEL_KEY = 'mapeiaai_final_bling_api_panel_v1'
UNIVERSAL_API_SEND_KEY = 'mapeiaai_universal_allow_api_send'
PLAIN_UNIVERSAL_FLOW_KINDS = {'universal_model_mapping'}
API_UNIVERSAL_FLOW_KINDS = {'universal_model_mapping_api'}
API_STATE_KEYS_TO_SUPPRESS = (
    FINAL_API_PANEL_KEY,
    'home_bling_connected_same_flow_api_send',
    'bling_connected_api_flow_active',
    'direct_bling_api_contract_active',
    'direct_bling_operation_applied',
    'direct_bling_api_contract_df',
    'bling_api_operation',
    'api_operation',
    'home_bling_api_operation_choice',
    'bling_connected_api_operation',
    'flow_spine_sender_operation',
    'flow_spine_sender_destination',
    'flow_spine_final_destination',
    'flow_spine_operation_resolved_for_api',
    'flow_spine_api_batch_operation',
    'source_first_selected_operation',
    'source_first_operation_user_confirmed',
    'source_first_operation_pending_choice',
    'bling_api_required_selector',
    'bling_api_final_action',
    'bling_api_manual_mapping_required',
    'bling_api_must_run_ai_check',
)


def _render_smartcore_box(result) -> None:
    if result is None:
        return
    quality = getattr(result, 'quality', None)
    if quality is None:
        return
    with st.expander('Validação inteligente opcional da saída final', expanded=False):
        st.caption(f'Origem: {getattr(result, "origin", "")} · Operação: {getattr(result, "operation", "")}')
        st.metric('Qualidade da saída', f'{quality.score}/100')
        for item in list(getattr(quality, 'warnings', []) or [])[:8]:
            st.warning(item)


def _render_smart_rules_report(report: Mapping[str, Any] | None) -> None:
    if not report:
        return
    with st.expander('Resumo das regras aplicadas', expanded=False):
        st.metric('Células ajustadas', int(report.get('applied_cells') or 0))
        image_cols = list(report.get('image_columns') or [])
        gtin_cols = list(report.get('gtin_columns') or [])
        if image_cols:
            st.caption('Imagens tratadas em: ' + ', '.join(map(str, image_cols)))
        if gtin_cols:
            st.caption('GTIN/EAN tratado em: ' + ', '.join(map(str, gtin_cols)))
        if report.get('limit_images'):
            st.caption(f'Limite de imagens por produto: {int(report.get("max_images") or 0)}')
        if report.get('validate_gtin'):
            st.caption('Validação de GTIN/EAN ligada.')


def _template_from_uploaded_widget() -> tuple[str, bytes] | None:
    for key in MODEL_TEMPLATE_UPLOAD_KEYS:
        uploaded = st.session_state.get(key)
        if uploaded is None:
            continue
        name = str(getattr(uploaded, 'name', '') or '').strip()
        try:
            data = uploaded.getvalue()
        except Exception:
            data = b''
        if name and data:
            return name, bytes(data)
    return None


def _template_from_stored_session() -> tuple[str, bytes] | None:
    for name_key in MODEL_TEMPLATE_NAME_KEYS:
        name = str(st.session_state.get(name_key) or '').strip()
        if not name:
            continue
        for bytes_key in MODEL_TEMPLATE_BYTES_KEYS:
            data = st.session_state.get(bytes_key)
            if isinstance(data, (bytes, bytearray)) and data:
                return name, bytes(data)
    return None


def _current_model_template() -> tuple[str, bytes] | None:
    return _template_from_uploaded_widget() or _template_from_stored_session()


def _suffix(file_name: str | None) -> str:
    return Path(str(file_name or '')).suffix.lower()


def _build_template_preserved_download(output: pd.DataFrame) -> tuple[bytes | None, str, str, bool, str]:
    template = _current_model_template()
    if template is None:
        return None, '', '', False, 'template_not_found'

    original_name, original_bytes = template
    try:
        resolved = resolver_modelo(original_name, original_bytes)
    except Exception as exc:
        return None, original_name, '', False, f'modelo_nao_resolvido:{str(exc)[:160]}'

    template_name = resolved.nome_planilha
    template_bytes = resolved.conteudo
    suffix = _suffix(template_name)
    if suffix not in SUPPORTED_PRESERVE_SUFFIXES:
        return None, template_name, '', False, f'formato_nao_compativel:{suffix or "sem_extensao"}'

    if not can_export_from_template(template_name, template_bytes):
        return None, template_name, '', False, 'exportador_indisponivel_para_modelo'

    file_bytes = build_template_download_bytes(template_bytes=template_bytes, template_name=template_name, df=output)
    status = f'compactado:{resolved.caminho_interno}' if resolved.origem_compactada else 'preserved'
    return file_bytes, output_name_for_template(template_name), mime_for_template_output(template_name), True, status


def _render_no_safe_download(template_name: str, template_suffix: str, preserve_status: str) -> None:
    st.session_state[DOWNLOAD_READY_KEY] = False
    if not template_name:
        st.error('Não encontrei o arquivo modelo original nesta sessão.')
        st.caption('Reanexe o modelo original em XLSX, XLSM, CSV ou um arquivo compactado contendo uma planilha aceita.')
        return
    if template_suffix == '.zip':
        st.error(f'O modelo compactado {template_name} não contém uma planilha interna compatível para download fiel.')
        st.caption(f'Use um arquivo compactado contendo CSV, XLSX ou XLSM. Status técnico: {preserve_status}.')
        return
    if template_suffix in EXCEL_LIKE_SUFFIXES and template_suffix not in SUPPORTED_PRESERVE_SUFFIXES:
        st.error(f'O modelo {template_name} está em formato {template_suffix.upper()} e ainda não pode ser preservado com segurança.')
        st.caption('Use XLSX, XLSM ou CSV para download fiel ao modelo original.')
        return
    if template_suffix in EXCEL_LIKE_SUFFIXES:
        st.error(f'Não consegui gerar o arquivo preservado a partir de {template_name}.')
        st.caption('Reanexe o modelo em XLSX, XLSM ou CSV. O CSV alternativo foi desativado para não quebrar o formato original.')
        return
    st.error(f'O modelo {template_name} não está em formato aceito para preservação fiel.')
    st.caption(f'Use XLSX, XLSM, CSV ou um arquivo compactado contendo uma planilha aceita. Status técnico: {preserve_status}.')


def _norm_column(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in text).split())


def _infer_bling_operation(output: pd.DataFrame) -> str:
    columns = {_norm_column(column) for column in output.columns} if isinstance(output, pd.DataFrame) else set()
    has_name = bool(columns & {'nome', 'produto', 'titulo', 'descricao', 'descricao produto', 'nome produto', 'nome do produto'})
    has_price = any('preco' in column or 'valor' in column for column in columns)
    has_qty = bool(columns & {'quantidade', 'qtd', 'qtde', 'saldo', 'estoque', 'balanco'})
    has_deposit = any('deposito' in column for column in columns)
    has_code = bool(columns & {'id', 'id produto', 'id bling', 'codigo', 'sku', 'referencia', 'gtin', 'ean'})
    has_channel = any(('canal' in column or 'loja' in column or 'marketplace' in column or 'produto loja' in column or 'vinculo loja' in column or 'preco destino' in column) for column in columns)
    has_catalog_richness = any(('categoria' in column or 'imagem' in column or 'marca' in column or 'departamento' in column or 'descricao curta' in column) for column in columns)
    if has_qty and (has_deposit or has_code):
        return OP_ESTOQUE
    if has_price and has_code and (has_channel or not has_catalog_richness):
        return OP_ATUALIZACAO_PRECO
    if has_name and has_price:
        return OP_CADASTRO
    return OP_UNIVERSAL


def _prepare_final_bling_snapshot(output: pd.DataFrame, operation: str, signature: str) -> pd.DataFrame:
    clean = output.copy().fillna('')
    st.session_state['final_download_df_snapshot'] = clean.copy()
    st.session_state['final_download_operation'] = operation
    st.session_state['df_final_download_operation'] = operation
    st.session_state['flow_spine_sender_operation'] = operation
    st.session_state['flow_spine_sender_destination'] = 'api_bling'
    st.session_state['flow_spine_final_destination'] = 'api_bling'
    st.session_state['home_bling_connected_same_flow_api_send'] = True
    st.session_state[FINAL_API_PANEL_KEY] = {'operation': operation, 'rows': int(len(clean)), 'signature': signature}
    return clean


def _render_price_api_targets(output: pd.DataFrame) -> None:
    try:
        from bling_app_zero.core.bling_price_sender_guarded import price_channel_targets
        summary = price_channel_targets(output)
    except Exception as exc:
        st.caption(f'Atualização de preços multiloja: não consegui listar lojas agora ({exc}).')
        return
    targets = list(summary.get('targets') or [])
    general_rows = int(summary.get('general_price_rows') or 0)
    unresolved = int(summary.get('unresolved_channel_rows') or 0)
    if not targets and general_rows <= 0:
        st.warning('Atualização de preços multiloja: nenhuma loja/canal foi identificada ainda. Confira a coluna de loja/canal ou ID do canal.')
        return
    st.info('Atualização de preços multiloja via API: o envio vai atualizar Preço e Preço promocional no vínculo produto-loja quando houver loja/canal.')
    if targets:
        with st.expander('Lojas/canais que serão atualizados via API', expanded=True):
            for item in targets[:12]:
                name = str(item.get('channel_name') or 'Loja/canal').strip()
                channel_id = str(item.get('channel_id') or '').strip()
                rows = int(item.get('rows') or 0)
                suffix = f' · ID {channel_id}' if channel_id else ' · ID será buscado/confirmado no Bling'
                st.caption(f'• {name}{suffix} · {rows} linha(s) · campos: preço + preço promocional')
            if len(targets) > 12:
                st.caption(f'… mais {len(targets) - 12} loja(s)/canal(is) agrupados.')
    if general_rows:
        st.caption(f'{general_rows} linha(s) sem loja/canal: serão tratadas como preço geral do produto.')
    if unresolved:
        st.warning(f'{unresolved} linha(s) pedem loja/canal, mas ainda não têm nome ou ID suficiente para identificar a loja no Bling.')


def _universal_api_send_allowed() -> bool:
    flow_kind = str(st.session_state.get('mapeiaai_flow_kind') or st.session_state.get('flow_kind') or '').strip()
    return bool(
        st.session_state.get(UNIVERSAL_API_SEND_KEY)
        or flow_kind in API_UNIVERSAL_FLOW_KINDS
        or st.session_state.get('api_flow_active') is True
        or st.session_state.get('home_bling_connected_same_flow_api_send') is True
    )


def _is_plain_universal_download_only() -> bool:
    if _universal_api_send_allowed():
        return False
    flow_kind = str(st.session_state.get('mapeiaai_flow_kind') or st.session_state.get('flow_kind') or '').strip()
    return bool(
        flow_kind in PLAIN_UNIVERSAL_FLOW_KINDS
        or st.session_state.get('mapear_planilha_sem_api_active') is True
        or st.session_state.get('active_feature_contract_key') == 'universal_mapping_csv'
    )


def _suppress_plain_universal_api_state(output: pd.DataFrame) -> None:
    for key in API_STATE_KEYS_TO_SUPPRESS:
        st.session_state.pop(key, None)
    add_audit_event(
        'shared_final_csv_api_panel_suppressed_download_only',
        area='BLING_API',
        status='BLOQUEADO',
        details={
            'reason': 'plain_universal_mapping_csv_download_only',
            'rows': int(len(output)) if isinstance(output, pd.DataFrame) else 0,
            'columns': list(map(str, output.columns)) if isinstance(output, pd.DataFrame) else [],
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_final_bling_api_panel(output: pd.DataFrame, *, key_prefix: str) -> None:
    if not isinstance(output, pd.DataFrame) or output.empty:
        return
    if _is_plain_universal_download_only():
        _suppress_plain_universal_api_state(output)
        st.info('Fluxo sem API: saída final liberada somente para download. Para enviar ao Bling, conecte ao Bling antes de entrar no fluxo Universal.')
        return
    operation = _infer_bling_operation(output)
    signature = f'{len(output)}x{len(output.columns)}:{pd.util.hash_pandas_object(output.head(80).fillna("").astype(str), index=True).sum()}'
    with st.container(border=True):
        st.markdown('### Enviar esta planilha tratada ao Bling')
        st.caption('Este botão usa exatamente a planilha final preenchida acima. A operação real é resolvida antes do envio; operação universal nunca é enviada direto para a API.')
        cols = st.columns(3)
        cols[0].metric('Linhas', int(len(output)))
        cols[1].metric('Colunas', int(len(output.columns)))
        cols[2].metric('Operação', 'Atualização de preços multiloja' if operation == OP_ATUALIZACAO_PRECO else operation_label(operation) if operation != OP_UNIVERSAL else 'A confirmar')

        if operation == OP_UNIVERSAL:
            st.warning('Envio bloqueado: não consegui identificar se a planilha é Cadastro, Estoque ou Atualização de preços.')
            add_audit_event('shared_final_bling_api_operation_not_detected', area='BLING_API', status='BLOQUEADO', details={'rows': int(len(output)), 'columns': list(map(str, output.columns)), 'responsible_file': RESPONSIBLE_FILE})
            return

        clean = _prepare_final_bling_snapshot(output, operation, signature)
        status = connection_status()
        if not status.get('connected'):
            st.warning('Bling ainda não conectado. Conecte para liberar o envio direto desta planilha final.')
            context = prepare_download_oauth_return(clean, operation, signature=signature)
            context.update({'return_to': 'download_panel', 'source_step': 'shared_final_csv', 'operation': operation, 'signature': signature})
            st.session_state['bling_oauth_return_context'] = dict(context)
            auth_url = build_authorization_url(context)
            render_new_tab_connect_button(auth_url)
            add_audit_event('shared_final_bling_api_waiting_connection', area='BLING_API', status='AGUARDANDO_CONEXAO', details={'operation': operation, 'rows': int(len(clean)), 'signature': signature, 'responsible_file': RESPONSIBLE_FILE})
            return

        st.success('Bling conectado. Envio direto liberado para esta planilha final tratada.')
        if operation == OP_ATUALIZACAO_PRECO:
            _render_price_api_targets(clean)
        render_bling_api_batch_panel(clean, operation, f'{key_prefix}_final_bling_api', signature, 'shared_final_csv')
        add_audit_event('shared_final_bling_api_panel_rendered', area='BLING_API', status='OK', details={'operation': operation, 'rows': int(len(clean)), 'signature': signature, 'responsible_file': RESPONSIBLE_FILE})


def apply_shared_text_rules(output: pd.DataFrame) -> pd.DataFrame:
    return apply_text_rules(output)


def build_shared_final_dataframe(source: pd.DataFrame, contract: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    return build_final_dataframe(source, contract, mapping)


def render_shared_final_csv(
    source: pd.DataFrame,
    contract: pd.DataFrame,
    mapping: dict[str, str],
    *,
    key_prefix: str = 'mapeiaai_shared_final',
    file_name: str = 'mapeiaai_planilha_final_mapeada.csv',
    run_smart_features: bool = True,
    smart_rules_config: Mapping[str, Any] | None = None,
) -> pd.DataFrame | None:
    result = build_final_output(
        source,
        contract,
        mapping,
        operation='universal',
        file_name=file_name,
        run_smart_features=bool(run_smart_features),
        smart_rules_config=smart_rules_config,
    )

    report = build_final_output_report(result)
    output = result.output
    st.session_state[FINAL_OUTPUT_REPORT_KEY] = report

    if output is None or not result.state.result.ok:
        st.session_state[DOWNLOAD_READY_KEY] = False
        st.error(result.state.result.message or 'Saída final bloqueada por erro de geração.')
        errors = list(result.errors or result.state.result.errors or [])
        for error in errors[:8]:
            st.warning(str(error))
        add_audit_event(
            'shared_final_csv_blocked',
            area='UNIVERSAL',
            status='BLOQUEADO',
            details={
                'errors': errors,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return None

    st.session_state[FINAL_OUTPUT_STATE_KEY] = output
    _render_smartcore_box(result.smartcore_result)
    st.dataframe(output.head(80), use_container_width=True, hide_index=True)

    csv_bytes = result.csv_bytes or output.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button('⬇️ Baixar CSV mapeado', data=csv_bytes, file_name=file_name, mime='text/csv; charset=utf-8', use_container_width=True, key=f'{key_prefix}_csv_download')

    template_bytes, template_output_name, template_mime, template_ok, preserve_status = _build_template_preserved_download(output)
    if template_ok and template_bytes:
        st.session_state[DOWNLOAD_READY_KEY] = True
        st.download_button(
            '⬇️ Baixar modelo original preenchido',
            data=template_bytes,
            file_name=template_output_name,
            mime=template_mime,
            use_container_width=True,
            key=f'{key_prefix}_template_preserved_download',
        )
    else:
        template = _current_model_template()
        template_name = template[0] if template else ''
        _render_no_safe_download(template_name, _suffix(template_name), preserve_status)

    _render_smart_rules_report(result.smart_rules_report)
    _render_final_bling_api_panel(output, key_prefix=key_prefix)
    return output


def render_final_csv_preview(df_final: pd.DataFrame, *, key_prefix: str = 'mapeiaai_final_csv') -> pd.DataFrame:
    st.session_state[FINAL_OUTPUT_STATE_KEY] = df_final
    st.dataframe(df_final.head(80), use_container_width=True, hide_index=True)
    csv_bytes = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button('⬇️ Baixar CSV mapeado', data=csv_bytes, file_name='mapeiaai_planilha_final_mapeada.csv', mime='text/csv; charset=utf-8', use_container_width=True, key=f'{key_prefix}_csv_download')
    _render_final_bling_api_panel(df_final, key_prefix=key_prefix)
    return df_final


__all__ = ['apply_shared_text_rules', 'build_shared_final_dataframe', 'render_final_csv_preview', 'render_shared_final_csv']
