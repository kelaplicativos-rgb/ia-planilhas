from __future__ import annotations

import math
import re
import zipfile
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.v2.exporter import to_csv_bytes
from bling_app_zero.v2.price_multistore.detector import detect_multistore_model
from bling_app_zero.v2.price_multistore.flow import run_multistore_price_flow
from bling_app_zero.v2.price_multistore.matcher import build_not_included_audit
from bling_app_zero.v2.price_multistore.shared_mapping import MultistoreMappingSelection, render_multistore_shared_mapping
from bling_app_zero.v2.session_store import get_state, pop_state, set_state, widget_key
from bling_app_zero.v2.store_profiles import build_store_profile
from bling_app_zero.v2.table_io import load_table
from bling_app_zero.v2.user_context import get_user_context

RESPONSIBLE_FILE = 'bling_app_zero/v2/price_multistore/ui.py'
PRICE_MULTISTORE_OPERATION_QP = 'price_multistore_v2'
MAX_IMPORT_ROWS = 200
MAX_BLING_IMPORT_ROWS = MAX_IMPORT_ROWS

CALCULATOR_MODES = ['Lucro nominal', 'Margem de contribuição', 'Preço fixo']
CALCULATOR_MODE_MAP = {'Lucro nominal': 'nominal_profit', 'Margem de contribuição': 'contribution_margin', 'Preço fixo': 'fixed_sale_price'}

DEFAULT_PROFILE_BASE: dict[str, Any] = {
    'store_id': '', 'calculator_mode_label': 'Lucro nominal', 'marketplace_fee': 14.0, 'tax': 8.0,
    'freight': 0.0, 'other_fees': 0.0, 'desired_nominal_profit': 15.0, 'desired_margin': 15.0,
    'desired_sale_price': 0.0, 'supplier_term': 15.0, 'stock_turnover': 30.0, 'promo': 0.0, 'custom': False,
}
DEFAULT_CHANNEL_LABELS = {
    'canal_1': 'Canal 1',
    'canal_2': 'Canal 2',
    'canal_3': 'Canal 3',
    'outro': 'Outro canal',
}
DEFAULT_CHANNEL_FEES = {key: 14.0 for key in DEFAULT_CHANNEL_LABELS}
DEFAULT_MARKETPLACE_LABELS = DEFAULT_CHANNEL_LABELS
DEFAULT_MARKETPLACE_FEES = DEFAULT_CHANNEL_FEES
NUMERIC_PROFILE_FIELDS = ['marketplace_fee', 'tax', 'freight', 'other_fees', 'desired_nominal_profit', 'desired_margin', 'desired_sale_price', 'supplier_term', 'stock_turnover', 'promo']
SITE_SOURCE_KEYS = ('df_site_bruto_precos', 'df_site_bruto_cadastro', 'df_site_bruto_estoque', 'df_origem_site_como_planilha_cadastro', 'df_origem_site_como_planilha_estoque', 'df_origem_site_como_planilha', 'df_site_bruto')
RESULT_KEYS = ('multistore_result_df', 'multistore_result_csv_bytes', 'multistore_not_included_audit_df', 'multistore_import_ready', 'multistore_last_ok', 'multistore_last_message', 'multistore_last_errors')


def _default_marketplace_profiles() -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for key, label in DEFAULT_CHANNEL_LABELS.items():
        profile = dict(DEFAULT_PROFILE_BASE)
        profile['label'] = label
        profile['marketplace_fee'] = DEFAULT_CHANNEL_FEES.get(key, 14.0)
        profiles[key] = profile
    return profiles


def _keep_multistore_route_alive() -> None:
    try:
        st.query_params['operation_v2'] = PRICE_MULTISTORE_OPERATION_QP
    except Exception:
        pass


def _read(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None

    files = uploaded_file if isinstance(uploaded_file, list) else [uploaded_file]
    frames: list[pd.DataFrame] = []

    for file in files:
        if file is None:
            continue
        filename = str(getattr(file, 'name', '') or 'arquivo')
        try:
            df = load_table(file).fillna('')
            if isinstance(df, pd.DataFrame) and not df.empty:
                df['_arquivo_origem'] = filename
                frames.append(df)
        except Exception as exc:
            st.error(f'Não consegui ler a planilha {filename}: {exc}')

    if not frames:
        return None

    return pd.concat(frames, ignore_index=True, sort=False).fillna('')


def _df_signature(df: pd.DataFrame | None) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 'empty'
    cols = '|'.join(map(str, df.columns))
    sample = pd.util.hash_pandas_object(df.head(200).astype(str), index=True).sum()
    return f'{len(df)}x{len(df.columns)}:{cols}:{sample}'


def _source_df_from_choice(choice: str, uploaded_file) -> pd.DataFrame | None:
    if choice == 'Site capturado':
        for key in SITE_SOURCE_KEYS:
            value = st.session_state.get(key)
            if isinstance(value, pd.DataFrame) and not value.empty:
                return value.copy().fillna('')
        return None
    return _read(uploaded_file)


def _clear_result_if_signature_changed(signature: str) -> None:
    previous = get_state('multistore_input_signature')
    if previous == signature:
        return
    set_state('multistore_input_signature', signature)
    for key in RESULT_KEYS:
        pop_state(key, None)


def _split_dataframe(df: pd.DataFrame, limit: int = MAX_IMPORT_ROWS) -> list[pd.DataFrame]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return [df.iloc[start:start + limit].copy().fillna('') for start in range(0, len(df), limit)]


def _csv_zip_bytes(parts: list[pd.DataFrame], prefix: str = 'atualizacao_precos') -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        total = len(parts)
        for index, part_df in enumerate(parts, start=1):
            zip_file.writestr(f'{prefix}_parte_{index:02d}_de_{total:02d}.csv', to_csv_bytes(part_df))
    return buffer.getvalue()


def _render_closed_preview(title: str, df: pd.DataFrame | None, *, rows: int = 80, height: int = 220) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        with st.expander(f'{title} · {len(df)} linha(s) × {len(df.columns)} coluna(s)', expanded=False):
            st.dataframe(df.head(rows).fillna(''), use_container_width=True, height=height)


def _render_alert(message: str) -> None:
    st.markdown(f'<div style="background:#fff7ed;border:1px solid #fed7aa;color:#7c2d12;border-radius:16px;padding:.9rem 1rem;font-weight:700;">⚠️ {message}</div>', unsafe_allow_html=True)


def _render_info(message: str) -> None:
    st.markdown(f'<div style="background:#f8fafc;border:1px solid #cbd5e1;color:#334155;border-radius:16px;padding:.9rem 1rem;font-weight:650;">{message}</div>', unsafe_allow_html=True)


def _render_success_action(message: str) -> None:
    st.markdown(f'<div style="margin-top:.75rem;background:#ecfdf5;border:1px solid #bbf7d0;color:#14532d;border-radius:16px;padding:.9rem 1rem;font-weight:700;">✅ {message}</div>', unsafe_allow_html=True)


def _render_bling_import_actions() -> None:
    _render_success_action('Planilha de preços pronta. Use os links personalizados do final do fluxo para abrir o destino de importação desejado.')


def _slugify(value: str) -> str:
    text = str(value or 'canal').strip().lower()
    text = text.translate(str.maketrans('áàãâäéèêëíìîïóòõôöúùûüç', 'aaaaaeeeeiiiiooooouuuuc'))
    return re.sub(r'[^a-z0-9]+', '_', text).strip('_') or 'canal'


def _profile_key_from_label(label: str, existing: dict[str, dict[str, Any]]) -> str:
    slug = _slugify(label)
    key = slug
    index = 2
    while key in existing:
        key = f'{slug}_{index}'
        index += 1
    return key


def _normalize_profile(raw: dict[str, Any], fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(DEFAULT_PROFILE_BASE)
    if fallback:
        base.update(fallback)
    base.update(dict(raw or {}))
    base['label'] = str(base.get('label') or 'Canal').strip()
    base['store_id'] = str(base.get('store_id') or '').strip()
    base['calculator_mode_label'] = str(base.get('calculator_mode_label') or 'Lucro nominal')
    if base['calculator_mode_label'] not in CALCULATOR_MODES:
        base['calculator_mode_label'] = 'Lucro nominal'
    for field in NUMERIC_PROFILE_FIELDS:
        try:
            base[field] = float(base.get(field, 0.0) or 0.0)
        except Exception:
            base[field] = float(DEFAULT_PROFILE_BASE.get(field, 0.0) or 0.0)
    base['custom'] = bool(base.get('custom', False))
    return base


def _marketplace_profiles() -> dict[str, dict[str, Any]]:
    profiles = _default_marketplace_profiles()
    saved = get_state('multistore_marketplace_profiles')
    if isinstance(saved, dict):
        for key, value in saved.items():
            if isinstance(value, dict):
                profiles[str(key)] = _normalize_profile(value, profiles.get(str(key)))
    set_state('multistore_marketplace_profiles', profiles)
    return profiles


def _save_marketplace_profiles(profiles: dict[str, dict[str, Any]]) -> None:
    set_state('multistore_marketplace_profiles', {str(key): _normalize_profile(value) for key, value in profiles.items()})


def _format_marketplace(value: str) -> str:
    return str(_marketplace_profiles().get(value, {}).get('label') or value.replace('_', ' ').title())


def _number_key(channel: str, field: str) -> str:
    return widget_key(f'multistore_{field}_{channel}')


def _field_widget_key(channel: str, field: str) -> str:
    return widget_key(f'multistore_{field}_{channel}')


def _sync_calculator_defaults(channel: str, profile: dict[str, Any]) -> None:
    if get_state('multistore_last_selected_channel') == channel:
        return
    set_state('multistore_last_selected_channel', channel)
    st.session_state[_field_widget_key(channel, 'store_name')] = str(profile.get('label') or _format_marketplace(channel))
    st.session_state[_field_widget_key(channel, 'store_id')] = str(profile.get('store_id') or '')
    st.session_state[_field_widget_key(channel, 'calculator_mode_label')] = str(profile.get('calculator_mode_label') or 'Lucro nominal')
    for field in NUMERIC_PROFILE_FIELDS:
        st.session_state[_number_key(channel, field)] = float(profile.get(field, 0.0) or 0.0)


def _current_profile_from_widgets(channel: str, profile: dict[str, Any]) -> dict[str, Any]:
    output = dict(profile)
    output['label'] = str(st.session_state.get(_field_widget_key(channel, 'store_name'), profile.get('label') or _format_marketplace(channel))).strip()
    output['store_id'] = str(st.session_state.get(_field_widget_key(channel, 'store_id'), profile.get('store_id') or '')).strip()
    output['calculator_mode_label'] = str(st.session_state.get(_field_widget_key(channel, 'calculator_mode_label'), profile.get('calculator_mode_label') or 'Lucro nominal'))
    for field in NUMERIC_PROFILE_FIELDS:
        output[field] = float(st.session_state.get(_number_key(channel, field), profile.get(field, 0.0)) or 0.0)
    output['custom'] = bool(profile.get('custom', False))
    return _normalize_profile(output, profile)


def _render_marketplace_manager(channel: str, profile: dict[str, Any]) -> None:
    profiles = _marketplace_profiles()
    with st.expander('Gerenciar lojas/canais e taxas salvas', expanded=False):
        col_save, col_delete = st.columns(2)
        with col_save:
            if st.button('Salvar taxas deste canal', use_container_width=True, key=widget_key(f'save_profile_{channel}')):
                profiles[channel] = _current_profile_from_widgets(channel, profile)
                _save_marketplace_profiles(profiles)
                st.success('Taxas salvas para este canal.')
                st.rerun()
        with col_delete:
            if st.button('Excluir canal selecionado', use_container_width=True, disabled=len(profiles) <= 1, key=widget_key(f'delete_profile_{channel}')):
                profiles.pop(channel, None)
                _save_marketplace_profiles(profiles)
                set_state('multistore_selected_channel', next(iter(profiles), 'outro'))
                set_state('multistore_last_selected_channel', '')
                st.success('Canal excluído.')
                st.rerun()
        st.markdown('##### Adicionar novo canal')
        new_name = st.text_input('Nome do novo canal', key=widget_key('new_marketplace_name'))
        c1, c2, c3 = st.columns(3)
        new_fee = c1.number_input('Taxa do canal %', min_value=0.0, value=14.0, step=0.5, key=widget_key('new_marketplace_fee'))
        new_tax = c2.number_input('Imposto %', min_value=0.0, value=8.0, step=0.5, key=widget_key('new_marketplace_tax'))
        new_profit = c3.number_input('Quero ganhar R$', min_value=0.0, value=15.0, step=0.5, key=widget_key('new_marketplace_profit'))
        if st.button('Adicionar canal', use_container_width=True, key=widget_key('add_marketplace_profile')):
            name = str(new_name or '').strip()
            if not name:
                _render_alert('Informe o nome do novo canal antes de adicionar.')
            else:
                key = _profile_key_from_label(name, profiles)
                new_profile = dict(DEFAULT_PROFILE_BASE)
                new_profile.update({'label': name, 'marketplace_fee': float(new_fee), 'tax': float(new_tax), 'desired_nominal_profit': float(new_profit), 'custom': True})
                profiles[key] = _normalize_profile(new_profile)
                _save_marketplace_profiles(profiles)
                set_state('multistore_selected_channel', key)
                set_state('multistore_last_selected_channel', '')
                st.success(f'Canal "{name}" adicionado.')
                st.rerun()


def _render_flow_explanation() -> None:
    context = get_user_context()
    _render_info('Este fluxo atualiza preços de produtos já vinculados a uma loja/canal. A origem do custo pode ser uma planilha ou uma captura por site já carregada. O cruzamento usa o mesmo mapeamento compartilhado do cadastro/estoque.')
    st.caption(f'Sessão isolada V2: {context.namespace}')


def _render_audit_download() -> None:
    audit_df = get_state('multistore_not_included_audit_df')
    if not isinstance(audit_df, pd.DataFrame) or audit_df.empty:
        st.success('Auditoria: nenhum produto ficou fora do cruzamento.')
        return
    st.markdown('### Auditoria · Produtos não incluídos')
    _render_alert(f'{len(audit_df)} produto(s) da origem não entraram na operação. Baixe esta planilha para conferência.')
    _render_closed_preview('Preview da auditoria dos produtos não incluídos', audit_df, rows=80, height=260)
    st.download_button('Baixar auditoria dos produtos não incluídos', data=to_csv_bytes(audit_df), file_name='auditoria_produtos_nao_incluidos_precos.csv', mime='text/csv; charset=utf-8', use_container_width=True, key=widget_key('multistore_audit_download'))


def _render_import_downloads(result_df: pd.DataFrame) -> None:
    parts = _split_dataframe(result_df, MAX_IMPORT_ROWS)
    if not parts:
        _render_alert('Nenhuma linha disponível para gerar planilha de importação.')
        return
    total_rows = len(result_df)
    total_parts = len(parts)
    set_state('multistore_result_csv_bytes', to_csv_bytes(result_df))
    if total_rows <= MAX_BLING_IMPORT_ROWS:
        _render_success_action(f'Arquivo dentro do limite do Bling: {total_rows} linha(s).')
        st.download_button('Baixar planilha limpa de preços', data=to_csv_bytes(result_df), file_name='atualizacao_precos.csv', mime='text/csv; charset=utf-8', use_container_width=True, key=widget_key('multistore_download'))
        return
    _render_alert(f'O resultado tem {total_rows} linhas. Como o Bling só importa até {MAX_BLING_IMPORT_ROWS} linhas por arquivo, o sistema dividiu em {total_parts} partes.')
    st.download_button(f'Baixar ZIP com {total_parts} planilhas de até {MAX_BLING_IMPORT_ROWS} linhas', data=_csv_zip_bytes(parts), file_name='atualizacao_precos_partes.zip', mime='application/zip', use_container_width=True, key=widget_key('multistore_download_zip_parts'))


def _render_ready_result(result_df: pd.DataFrame) -> None:
    _keep_multistore_route_alive()
    st.markdown('### Etapa 6 · Conferência')
    preview_cols = [column for column in ['IdProduto', 'ID na Loja', 'Preço', 'Preco', 'Preço Promocional', 'Preco Promocional', 'Nome da Loja'] if column in result_df.columns]
    _render_closed_preview('Preview final limpo para importação', result_df[preview_cols].copy() if preview_cols else result_df.copy(), rows=80, height=340)
    total_parts = max(1, math.ceil(len(result_df) / MAX_BLING_IMPORT_ROWS)) if len(result_df) else 0
    st.caption(f'{len(result_df)} linha(s) prontas para importação · {total_parts} arquivo(s) respeitando o limite do Bling de {MAX_BLING_IMPORT_ROWS} linhas por arquivo.')
    _render_audit_download()
    st.markdown('### Etapa 7 · Download e importação')
    _render_info('Baixe os arquivos limpos. Quando passar de 200 linhas, o sistema divide automaticamente em partes compatíveis com o Bling.')
    _render_import_downloads(result_df)
    _render_bling_import_actions()


def render_price_multistore_v2() -> None:
    _keep_multistore_route_alive()
    st.markdown('## 🏬 Atualizar preços por loja/canal')
    _render_flow_explanation()
    profiles = _marketplace_profiles()
    options = list(profiles.keys())
    st.markdown('### Etapa 1 · Loja / canal')
    selected_channel = get_state('multistore_selected_channel')
    channel = st.selectbox('Qual loja/canal você quer atualizar?', options, index=options.index(selected_channel) if selected_channel in options else 0, format_func=_format_marketplace, key=widget_key('multistore_channel'))
    set_state('multistore_selected_channel', channel)
    profile = profiles.get(channel, _default_marketplace_profiles()['outro'])
    _sync_calculator_defaults(channel, profile)
    c_store_1, c_store_2 = st.columns(2)
    store_name = c_store_1.text_input('Nome da loja/canal', key=_field_widget_key(channel, 'store_name'))
    store_id = c_store_2.text_input('ID da loja/canal, se houver', key=_field_widget_key(channel, 'store_id'))
    st.caption('Trabalhe com uma loja/canal por vez para evitar mistura de taxas, anúncios e identificadores.')
    _render_marketplace_manager(channel, profile)

    st.markdown('### Etapa 2 · Modelo de preços')
    model_upload = st.file_uploader('Planilha 1 — Modelo de preços', type=['csv', 'xlsx', 'xls', 'zip'], accept_multiple_files=True, key=widget_key('multistore_model_upload'))
    model_df = _read(model_upload)
    if isinstance(model_df, pd.DataFrame):
        detection = detect_multistore_model(model_df)
        if detection.is_multistore:
            st.success(f'Modelo de preços reconhecido · {len(model_df)} linha(s) × {len(model_df.columns)} coluna(s).')
            _render_closed_preview('Preview da Planilha 1', model_df, rows=12, height=180)
        else:
            _render_alert(detection.message + ' Faltando: ' + ', '.join(detection.missing))
            return
    else:
        result_df = get_state('multistore_result_df')
        if isinstance(result_df, pd.DataFrame) and not result_df.empty:
            _render_ready_result(result_df.copy().fillna(''))
            return
        _render_alert('Anexe uma ou mais planilhas do Modelo de preços para continuar.')
        return

    st.markdown('### Etapa 3 · Origem do custo')
    source_origin = st.radio('Origem dos dados de custo', ['Arquivo', 'Site capturado'], horizontal=True, key=widget_key('multistore_source_origin'))
    source_upload = None
    if source_origin == 'Arquivo':
        source_upload = st.file_uploader('Planilha 2 — Origem de custo dos produtos', type=['csv', 'xlsx', 'xls', 'zip'], accept_multiple_files=True, key=widget_key('multistore_source_upload'))
    else:
        st.caption('Usa a última captura por site salva na sessão. Primeiro faça a captura por site no fluxo de origem, depois volte para preços por loja/canal.')
    source_df = _source_df_from_choice(source_origin, source_upload)
    if isinstance(source_df, pd.DataFrame) and not source_df.empty:
        st.success(f'Origem de custo carregada por {source_origin.lower()} · {len(source_df)} linha(s) × {len(source_df.columns)} coluna(s).')
        _render_closed_preview('Preview da origem/custo', source_df, rows=12, height=180)
    else:
        _render_alert('Para calcular, carregue uma ou mais origens de custo por arquivo ou por site capturado.')

    mapping = render_multistore_shared_mapping(model_df, source_df if isinstance(source_df, pd.DataFrame) else pd.DataFrame())
    signature = f'{source_origin}|{_df_signature(model_df)}|{_df_signature(source_df)}|{mapping.model_identifier_column}|{mapping.source_identifier_column}|{mapping.source_cost_column}'
    _clear_result_if_signature_changed(signature)
    can_generate = isinstance(source_df, pd.DataFrame) and not source_df.empty and isinstance(mapping, MultistoreMappingSelection) and mapping.ready

    st.markdown('### Etapa 5 · Calculadora plugável')
    calculator_mode = st.radio('Como deseja calcular?', CALCULATOR_MODES, horizontal=True, key=_field_widget_key(channel, 'calculator_mode_label'))
    calculator_mode_key = CALCULATOR_MODE_MAP[calculator_mode]
    c1, c2, c3, c4 = st.columns(4)
    marketplace_fee = c1.number_input('Taxa do canal %', min_value=0.0, step=0.5, key=_number_key(channel, 'marketplace_fee'))
    tax = c2.number_input('Imposto %', min_value=0.0, step=0.5, key=_number_key(channel, 'tax'))
    freight = c3.number_input('Frete R$', min_value=0.0, step=0.5, key=_number_key(channel, 'freight'))
    other_fees = c4.number_input('Outras taxas %', min_value=0.0, step=0.5, key=_number_key(channel, 'other_fees'))
    c5, c6, c7, c8 = st.columns(4)
    if calculator_mode_key == 'nominal_profit':
        desired_nominal_profit = c5.number_input('Quero ganhar R$', min_value=0.0, step=0.5, key=_number_key(channel, 'desired_nominal_profit'))
        desired_margin = float(st.session_state.get(_number_key(channel, 'desired_margin'), profile.get('desired_margin', 0.0)) or 0.0)
        desired_sale_price = float(st.session_state.get(_number_key(channel, 'desired_sale_price'), profile.get('desired_sale_price', 0.0)) or 0.0)
    elif calculator_mode_key == 'contribution_margin':
        desired_margin = c5.number_input('Quero margem de %', min_value=0.0, step=0.5, key=_number_key(channel, 'desired_margin'))
        desired_nominal_profit = float(st.session_state.get(_number_key(channel, 'desired_nominal_profit'), profile.get('desired_nominal_profit', 0.0)) or 0.0)
        desired_sale_price = float(st.session_state.get(_number_key(channel, 'desired_sale_price'), profile.get('desired_sale_price', 0.0)) or 0.0)
    else:
        desired_sale_price = c5.number_input('Quero vender por R$', min_value=0.0, step=0.5, key=_number_key(channel, 'desired_sale_price'))
        desired_nominal_profit = float(st.session_state.get(_number_key(channel, 'desired_nominal_profit'), profile.get('desired_nominal_profit', 0.0)) or 0.0)
        desired_margin = float(st.session_state.get(_number_key(channel, 'desired_margin'), profile.get('desired_margin', 0.0)) or 0.0)
    supplier_term = c6.number_input('Prazo fornecedor (dias)', min_value=0.0, step=1.0, key=_number_key(channel, 'supplier_term'))
    stock_turnover = c7.number_input('Giro estoque (dias)', min_value=0.0, step=1.0, key=_number_key(channel, 'stock_turnover'))
    promo = c8.number_input('Promo %', min_value=0.0, step=0.5, key=_number_key(channel, 'promo'))
    if st.button('Salvar taxas atuais para este canal', use_container_width=True, key=widget_key(f'save_profile_below_calc_{channel}')):
        profiles = _marketplace_profiles()
        profiles[channel] = _current_profile_from_widgets(channel, profile)
        _save_marketplace_profiles(profiles)
        st.success('Taxas atuais salvas para este canal.')
        st.rerun()
    pricing_rules = {
        'calculator_mode': calculator_mode_key, 'marketplace_fee_percent': marketplace_fee, 'commission_percent': marketplace_fee,
        'tax_percent': tax, 'freight_cost': freight, 'other_sale_fees_percent': other_fees,
        'desired_nominal_profit': desired_nominal_profit, 'desired_contribution_margin_percent': desired_margin,
        'desired_sale_price': desired_sale_price, 'supplier_term_days': supplier_term, 'stock_turnover_days': stock_turnover,
        'promo_discount_percent': promo,
    }
    profile_for_run = build_store_profile(channel, store_id=store_id, name=store_name, overrides={'pricing_rules': pricing_rules})
    if not can_generate:
        _render_alert('A geração fica bloqueada até carregar a origem e concluir o mapeamento compartilhado.')
    if st.button('Gerar prévia de preços', use_container_width=True, key=widget_key('multistore_generate'), disabled=not can_generate):
        result = run_multistore_price_flow(model_df, profile_for_run, source_df, mapping.source_cost_column, pricing_rules, model_identifier_column=mapping.model_identifier_column, source_identifier_column=mapping.source_identifier_column)
        set_state('multistore_last_ok', result.ok)
        set_state('multistore_last_message', result.message)
        set_state('multistore_last_errors', list(result.errors))
        if result.ok:
            result_df = result.payload.df.copy().fillna('')
            audit_df = build_not_included_audit(model_df, source_df, mapping.source_cost_column, model_identifier_column=mapping.model_identifier_column, source_identifier_column=mapping.source_identifier_column)
            set_state('multistore_result_df', result_df)
            set_state('multistore_result_csv_bytes', to_csv_bytes(result_df))
            set_state('multistore_not_included_audit_df', audit_df)
            set_state('multistore_import_ready', True)
        else:
            for key in ('multistore_result_df', 'multistore_result_csv_bytes', 'multistore_not_included_audit_df'):
                pop_state(key, None)
            set_state('multistore_import_ready', False)
        st.rerun()
    if get_state('multistore_last_message'):
        if get_state('multistore_last_ok'):
            st.success(get_state('multistore_last_message'))
        else:
            _render_alert(get_state('multistore_last_message'))
            for error in get_state('multistore_last_errors', []):
                st.caption(f'• {error}')
    result_df = get_state('multistore_result_df')
    if isinstance(result_df, pd.DataFrame) and not result_df.empty:
        _render_ready_result(result_df.copy().fillna(''))


__all__ = ['render_price_multistore_v2']
