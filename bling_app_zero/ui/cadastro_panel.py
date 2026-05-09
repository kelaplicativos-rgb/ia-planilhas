from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from bling_app_zero.core.ai_mapping_assistant import (
    ai_mapping_enabled,
    apply_ai_mapping_assist,
    merge_ai_suggestions,
)
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping
from bling_app_zero.core.mapping_confidence import (
    confidence_for_mapping,
    resolved_empty_confidence,
    sort_targets_by_confidence,
)
from bling_app_zero.core.mapping_super_assistant import super_auto_map_columns
from bling_app_zero.core.pricing import detect_discount_percent
from bling_app_zero.core.text import normalize_key
from bling_app_zero.engines.cadastro_engine import default_model
from bling_app_zero.engines.estoque_engine import default_model as estoque_default_model
from bling_app_zero.flows.site_as_source import (
    get_site_estoque_model,
    get_site_model_for_operation,
    get_site_source_for_operation,
)
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model, save_home_models
from bling_app_zero.ui.home_shared import (
    df_signature,
    download_final,
    load_apply_pricing,
    preview_df,
    show_mapping,
)
from bling_app_zero.ui.mapping_layout import inject_mapping_css, render_mapping_preview, render_mapping_title
from bling_app_zero.ui.smart_upload import render_smart_upload_box

EMPTY_CHOOSE_OPTION = '— escolher coluna —'
EMPTY_LEAVE_OPTION = '— deixar vazio —'
DEFAULT_PROFIT_PERCENT = 50.0

PRICE_TARGET_ALIASES = [
    'Preço de venda',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Valor',
]


def _option_value(value: str | None) -> str:
    text = str(value or '').strip()
    if text in {EMPTY_CHOOSE_OPTION, EMPTY_LEAVE_OPTION}:
        return ''
    return text


def _display_option(value: str | None) -> str:
    text = str(value or '').strip()
    if not text:
        return EMPTY_LEAVE_OPTION
    return text


def _is_explicit_empty(widget_key: str, value: str | None) -> bool:
    return str(value or '').strip() == EMPTY_LEAVE_OPTION or bool(st.session_state.get(f'{widget_key}__empty_resolved'))


def _confidence_for_selection(df_source: pd.DataFrame, target: str, selected: str, widget_key: str) -> dict[str, object]:
    if _is_explicit_empty(widget_key, selected):
        return resolved_empty_confidence()
    return confidence_for_mapping(df_source, target, _option_value(selected))


def _apply_calculated_price_aliases(df: pd.DataFrame, calculated_column: str = 'Preço de venda') -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or calculated_column not in df.columns:
        return df
    out = df.copy().fillna('')
    calculated_values = out[calculated_column]
    for column in PRICE_TARGET_ALIASES:
        out[column] = calculated_values
    return out


def _best_cost_column(columns: list[str]) -> int:
    preferred_terms = ['custo', 'preço custo', 'preco custo', 'valor produto', 'valor', 'preço', 'preco', 'price']
    lower_columns = [column.lower() for column in columns]
    for term in preferred_terms:
        for index, column in enumerate(lower_columns):
            if term in column:
                return index
    return 0


def _sync_detected_discount(df_origem: pd.DataFrame, signature: str) -> float:
    detected = float(detect_discount_percent(df_origem) or 0.0)
    previous_signature = st.session_state.get('cadastro_precificacao_signature')
    if previous_signature != signature:
        st.session_state['cadastro_precificacao_signature'] = signature
        st.session_state['cadastro_desconto_comissao'] = detected
    if 'cadastro_desconto_comissao' not in st.session_state:
        st.session_state['cadastro_desconto_comissao'] = detected
    return detected


def _cadastro_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return df_modelo
    return default_model()


def _estoque_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return df_modelo
    return estoque_default_model()


def _select_cadastro_model(upload) -> pd.DataFrame | None:
    site_model = get_site_model_for_operation('cadastro')
    if isinstance(site_model, pd.DataFrame):
        return site_model
    home_model = get_home_cadastro_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.cadastro_model_df, pd.DataFrame):
        save_home_models(upload.cadastro_model_df, upload.estoque_model_df)
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        save_home_models(upload.model_df, upload.estoque_model_df)
        return upload.model_df
    return None


def _select_estoque_model(upload) -> pd.DataFrame | None:
    site_model = get_site_estoque_model()
    if isinstance(site_model, pd.DataFrame):
        return site_model
    home_model = get_home_estoque_model()
    if isinstance(home_model, pd.DataFrame):
        return home_model
    if isinstance(upload.estoque_model_df, pd.DataFrame):
        save_home_models(upload.cadastro_model_df if isinstance(upload.cadastro_model_df, pd.DataFrame) else upload.model_df, upload.estoque_model_df)
        return upload.estoque_model_df
    return None


def _default_index(options: list[str], value: str, widget_key: str | None = None) -> int:
    if widget_key and st.session_state.get(f'{widget_key}__empty_resolved'):
        return options.index(EMPTY_LEAVE_OPTION) if EMPTY_LEAVE_OPTION in options else 0
    display = _display_option(value)
    try:
        return options.index(display)
    except ValueError:
        return 0


def _first_row_preview(df_source: pd.DataFrame, selected_column: str) -> str:
    selected_column = _option_value(selected_column)
    if not selected_column or selected_column not in df_source.columns or df_source.empty:
        return ''
    value = df_source[selected_column].iloc[0]
    text = str(value if value is not None else '').strip()
    if len(text) > 160:
        text = text[:160] + '...'
    return text


def _render_mapping_preview(df_source: pd.DataFrame, selected_column: str) -> None:
    render_mapping_preview(_first_row_preview(df_source, selected_column))


def _show_first_row_preview(df_source: pd.DataFrame, selected_column: str) -> None:
    # Usado fora do mapeamento, por exemplo na calculadora.
    text = _first_row_preview(df_source, selected_column)
    if not text:
        return
    safe_text = html.escape(text)
    st.markdown(
        f"<div style='font-size:12px; color:#118a32; margin-top:2px; margin-bottom:4px; font-weight:750; overflow-wrap:anywhere;'>{safe_text}</div>",
        unsafe_allow_html=True,
    )


def _signal_label(target: str, info: dict[str, object]) -> str:
    emoji = str(info.get('emoji') or '🔴')
    return f'{emoji} {target}'


def _current_confidence_from_widgets(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for target in target_columns:
        widget_key = f'{mapping_key}_{target}'
        selected = st.session_state.get(widget_key, current_mapping.get(target, ''))
        result[target] = _confidence_for_selection(df_source, target, selected, widget_key)
    return result


def _force_price_suggestion(target: str, source_columns: list[str], suggested: str) -> str:
    if target in PRICE_TARGET_ALIASES and 'Preço de venda' in source_columns:
        return 'Preço de venda'
    return suggested


def _build_super_mapping(df_source: pd.DataFrame, model: pd.DataFrame, source_columns: list[str]) -> dict[str, str]:
    auto_mapping = super_auto_map_columns(df_source, model)
    for target, selected in list(auto_mapping.items()):
        auto_mapping[target] = _force_price_suggestion(target, source_columns, selected)
    return auto_mapping


def _fill_deposito_manual(df: pd.DataFrame, deposito: str) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if not deposito:
        return out
    for column in out.columns:
        if 'deposito' in normalize_key(column):
            out[column] = deposito
    return out


def _clear_mapping_widgets(mapping_key: str) -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith(f'{mapping_key}_'):
            st.session_state.pop(key, None)


def _apply_ai_to_session_mapping(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
) -> None:
    result = apply_ai_mapping_assist(df_source, target_columns, current_mapping, only_uncertain=True)
    if not result.enabled:
        st.warning('IA de mapeamento não configurada. Adicione OPENAI_API_KEY nos secrets do Streamlit.')
        return
    if result.applied <= 0:
        st.info('A IA não encontrou sugestões seguras para aplicar.')
        return
    st.session_state[mapping_key] = merge_ai_suggestions(current_mapping, result)
    _clear_mapping_widgets(mapping_key)
    st.success(f'IA aplicou {result.applied} sugestão(ões) validadas pelo motor local.')
    st.rerun()


def _render_ai_button(df_source: pd.DataFrame, target_columns: list[str], current_mapping: dict[str, str], mapping_key: str, label: str) -> None:
    if not ai_mapping_enabled():
        st.caption('IA opcional inativa: configure OPENAI_API_KEY nos secrets para usar assistência GPT nos pendentes.')
        return
    if st.button(label, use_container_width=True):
        _apply_ai_to_session_mapping(df_source, target_columns, current_mapping, mapping_key)


def _render_mapping_select(
    df_source: pd.DataFrame,
    target: str,
    suggested: str,
    mapping_key: str,
    options: list[str],
) -> tuple[str, dict[str, object]]:
    widget_key = f'{mapping_key}_{target}'
    if widget_key in st.session_state:
        suggested = _option_value(st.session_state.get(widget_key, suggested))

    raw_before = st.session_state.get(widget_key, suggested)
    info_before = _confidence_for_selection(df_source, target, raw_before, widget_key)
    label = _signal_label(target, info_before)

    with st.container(border=True):
        render_mapping_title(label)
        selected_raw = st.selectbox(
            target,
            options,
            index=_default_index(options, suggested, widget_key),
            key=widget_key,
            label_visibility='collapsed',
        )

        if selected_raw == EMPTY_LEAVE_OPTION:
            st.session_state[f'{widget_key}__empty_resolved'] = True
        else:
            st.session_state.pop(f'{widget_key}__empty_resolved', None)

        selected = _option_value(selected_raw)
        info_after = _confidence_for_selection(df_source, target, selected_raw, widget_key)
        _render_mapping_preview(df_source, selected)

    return selected, info_after


def _render_manual_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    inject_mapping_css()
    model = _cadastro_model(df_modelo)
    source_columns = [str(column) for column in df_source.columns]
    target_columns = [str(column) for column in model.columns]
    options = [EMPTY_LEAVE_OPTION] + source_columns
    signature = df_signature(df_source) + ':' + '|'.join(target_columns)
    mapping_key = f'cadastro_manual_mapping_{signature}'

    if mapping_key not in st.session_state:
        st.session_state[mapping_key] = _build_super_mapping(df_source, model, source_columns)

    st.markdown('#### 2. Conferir colunas')
    st.caption('🔴 escolher coluna · 🟡 revisar · 🟢 seguro/vazio resolvido no final')
    with st.expander('Ver origem', expanded=False):
        preview_df('Origem para conferir', df_source)

    current_mapping = dict(st.session_state.get(mapping_key, {}))
    _render_ai_button(df_source, target_columns, current_mapping, mapping_key, 'Usar IA nos pendentes')
    current_confidence = _current_confidence_from_widgets(df_source, target_columns, current_mapping, mapping_key)
    ordered_targets = sort_targets_by_confidence(target_columns, current_confidence)
    edited_mapping: dict[str, str] = {}
    edited_confidence: dict[str, dict[str, object]] = {}

    for target in ordered_targets:
        selected, info_after = _render_mapping_select(
            df_source=df_source,
            target=target,
            suggested=current_mapping.get(target, ''),
            mapping_key=mapping_key,
            options=options,
        )
        edited_mapping[target] = selected
        edited_confidence[target] = info_after

    st.session_state[mapping_key] = edited_mapping
    st.session_state['mapping_confidence_cadastro'] = edited_confidence
    df_preview_manual = sanitize_for_bling(apply_mapping(df_source, model, edited_mapping))
    st.session_state['df_final_cadastro'] = df_preview_manual
    st.session_state['mapping_cadastro'] = edited_mapping

    used_values = [value for value in edited_mapping.values() if value]
    duplicated = sorted({value for value in used_values if used_values.count(value) > 1})
    if duplicated:
        st.warning('A mesma coluna foi usada mais de uma vez: ' + ', '.join(duplicated))

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Atualizar cadastro', use_container_width=True):
            st.rerun()
    with col_b:
        if st.button('Remapear com motor inteligente', use_container_width=True):
            st.session_state[mapping_key] = _build_super_mapping(df_source, model, source_columns)
            st.session_state.pop('df_final_cadastro', None)
            st.session_state.pop('mapping_cadastro', None)
            st.session_state.pop('mapping_confidence_cadastro', None)
            _clear_mapping_widgets(mapping_key)
            st.rerun()


def _render_manual_stock_mapping(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None, deposito: str) -> None:
    inject_mapping_css()
    model = _estoque_model(df_modelo_estoque)
    source_columns = [str(column) for column in df_source.columns]
    target_columns = [str(column) for column in model.columns]
    options = [EMPTY_LEAVE_OPTION] + source_columns
    signature = df_signature(df_source) + ':' + '|'.join(target_columns) + f':{deposito}'
    mapping_key = f'estoque_manual_mapping_from_cadastro_{signature}'

    if mapping_key not in st.session_state:
        auto_mapping = super_auto_map_columns(df_source, model)
        for target in target_columns:
            if 'deposito' in normalize_key(target):
                auto_mapping[target] = ''
        st.session_state[mapping_key] = auto_mapping

    st.markdown('##### Conferir estoque')
    st.caption('🔴 escolher coluna · 🟡 revisar · 🟢 seguro/vazio resolvido no final')
    with st.expander('Ver origem do estoque', expanded=False):
        preview_df('Origem para estoque', df_source)

    current_mapping = dict(st.session_state.get(mapping_key, {}))
    _render_ai_button(df_source, target_columns, current_mapping, mapping_key, 'Usar IA no estoque pendente')
    current_confidence = _current_confidence_from_widgets(df_source, target_columns, current_mapping, mapping_key)
    ordered_targets = sort_targets_by_confidence(target_columns, current_confidence)
    edited_mapping: dict[str, str] = {}
    edited_confidence: dict[str, dict[str, object]] = {}

    for target in ordered_targets:
        target_key = normalize_key(target)
        widget_key = f'{mapping_key}_{target}'
        if 'deposito' in target_key:
            with st.container(border=True):
                render_mapping_title('🟢 ' + target)
                st.text_input(target, value=deposito, disabled=True, key=f'{widget_key}_deposito_visual', label_visibility='collapsed')
            edited_mapping[target] = ''
            edited_confidence[target] = {'level': 'verde', 'emoji': '🟢', 'label': '100% seguro', 'score': 100, 'order': 2}
            continue
        selected, info_after = _render_mapping_select(
            df_source=df_source,
            target=target,
            suggested=current_mapping.get(target, ''),
            mapping_key=mapping_key,
            options=options,
        )
        edited_mapping[target] = selected
        edited_confidence[target] = info_after

    st.session_state[mapping_key] = edited_mapping
    st.session_state['mapping_confidence_estoque_from_cadastro'] = edited_confidence
    df_preview_manual = apply_mapping(df_source, model, edited_mapping)
    df_preview_manual = _fill_deposito_manual(df_preview_manual, deposito)
    df_preview_manual = sanitize_for_bling(df_preview_manual)
    st.session_state['df_final_estoque_from_cadastro'] = df_preview_manual
    st.session_state['mapping_estoque_from_cadastro'] = edited_mapping

    used_values = [value for value in edited_mapping.values() if value]
    duplicated = sorted({value for value in used_values if used_values.count(value) > 1})
    if duplicated:
        st.warning('A mesma coluna foi usada mais de uma vez no estoque: ' + ', '.join(duplicated))

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Atualizar estoque', use_container_width=True):
            st.rerun()
    with col_b:
        if st.button('Remapear estoque inteligente', use_container_width=True):
            st.session_state.pop(mapping_key, None)
            st.session_state.pop('df_final_estoque_from_cadastro', None)
            st.session_state.pop('mapping_estoque_from_cadastro', None)
            st.session_state.pop('mapping_confidence_estoque_from_cadastro', None)
            _clear_mapping_widgets(mapping_key)
            st.rerun()


def _render_dual_stock_output(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None) -> None:
    st.markdown('#### Estoque')
    if not isinstance(df_modelo_estoque, pd.DataFrame) or not len(df_modelo_estoque.columns):
        st.info('Anexe o modelo de estoque no passo inicial para gerar também a planilha de estoque.')
        st.session_state.pop('df_final_estoque_from_cadastro', None)
        st.session_state.pop('mapping_estoque_from_cadastro', None)
        return
    st.success('Modelo de estoque detectado.')
    deposito = st.text_input('Depósito', value='Não definido', key='cadastro_deposito_estoque_mesma_origem')
    _render_manual_stock_mapping(df_source, df_modelo_estoque, deposito)
    mapping_estoque = st.session_state.get('mapping_estoque_from_cadastro', {})
    df_final_estoque = st.session_state.get('df_final_estoque_from_cadastro')
    if isinstance(mapping_estoque, dict):
        show_mapping(mapping_estoque)
    if isinstance(df_final_estoque, pd.DataFrame):
        preview_df('Preview final do estoque', df_final_estoque)
        download_final(df_final_estoque, 'estoque', 'estoque_from_cadastro')


def _render_source_upload(df_origem_site: pd.DataFrame | None):
    home_has_models = get_home_cadastro_model() is not None or get_home_estoque_model() is not None
    allow_model_upload = not home_has_models
    if isinstance(df_origem_site, pd.DataFrame):
        st.success('Planilha criada pelo site carregada. Continue o fluxo normalmente.')
        st.caption('Nenhum modelo será pedido novamente neste fluxo.')
        return render_smart_upload_box(
            title='Arquivo complementar do fornecedor',
            operation='cadastro',
            key='smart_upload_cadastro',
            allow_model=allow_model_upload,
            required_model=False,
            accepted_types=['xlsx', 'xls', 'csv', 'xml', 'pdf'],
        )
    st.markdown('### Enviar arquivo do fornecedor')
    st.caption('Anexe planilha, PDF ou XML com os produtos.')
    if home_has_models:
        st.success('Modelos do Bling carregados no passo inicial. Agora envie somente o arquivo do fornecedor.')
    return render_smart_upload_box(
        title='Arquivos do fornecedor',
        operation='cadastro',
        key='smart_upload_cadastro',
        allow_model=allow_model_upload,
        required_model=False,
        accepted_types=['xlsx', 'xls', 'csv', 'xml', 'pdf'],
    )


def render_cadastro_panel() -> None:
    df_origem_site = get_site_source_for_operation('cadastro')
    upload = _render_source_upload(df_origem_site)
    df_origem = df_origem_site if isinstance(df_origem_site, pd.DataFrame) else upload.source_df
    df_modelo = _select_cadastro_model(upload)
    df_modelo_estoque = _select_estoque_model(upload)

    if isinstance(df_origem, pd.DataFrame) and not df_origem.empty:
        if isinstance(df_modelo, pd.DataFrame) and isinstance(df_modelo_estoque, pd.DataFrame):
            st.success('Cadastro e estoque detectados. O sistema vai gerar os dois arquivos.')
        usar_preco = st.checkbox('Aplicar calculadora de preço', value=False)
        if usar_preco:
            apply_pricing = load_apply_pricing()
            colunas = [str(c) for c in df_origem.columns]
            origem_signature = df_signature(df_origem)
            desconto_detectado = _sync_detected_discount(df_origem, origem_signature)
            coluna_custo = st.selectbox('Coluna de custo/preço base', colunas, index=_best_cost_column(colunas), key=f'cadastro_coluna_custo_{origem_signature}')
            _show_first_row_preview(df_origem, coluna_custo)
            if desconto_detectado > 0:
                st.info(f'Desconto/comissão detectado: {desconto_detectado:.2f}%')
            c1, c2, c3, c4, c5 = st.columns(5)
            margem = c1.number_input('Lucro %', min_value=0.0, value=DEFAULT_PROFIT_PERCENT, step=1.0, key=f'cadastro_margem_{origem_signature}')
            imposto = c2.number_input('Impostos %', min_value=0.0, value=0.0, step=1.0, key=f'cadastro_imposto_{origem_signature}')
            taxa = c3.number_input('Taxas %', min_value=0.0, value=0.0, step=1.0, key=f'cadastro_taxa_{origem_signature}')
            desconto = c4.number_input('Desconto %', min_value=0.0, step=1.0, key='cadastro_desconto_comissao')
            fixo = c5.number_input('Fixo R$', min_value=0.0, value=0.0, step=1.0, key=f'cadastro_fixo_{origem_signature}')
            df_origem = apply_pricing(df_origem, coluna_custo, 'Preço de venda', margem, imposto, taxa, fixo, desconto)
            df_origem = _apply_calculated_price_aliases(df_origem, 'Preço de venda')
            st.session_state['cadastro_preco_calculado_ativo'] = True
            st.session_state['df_origem_cadastro_precificada'] = df_origem
            with st.expander('Ver preço calculado', expanded=False):
                preview_df('Origem com preço calculado', df_origem)
        else:
            st.session_state['cadastro_preco_calculado_ativo'] = False
            st.session_state.pop('df_origem_cadastro_precificada', None)
        df_para_mapear = st.session_state.get('df_origem_cadastro_precificada', df_origem)
        _render_manual_mapping(df_para_mapear, df_modelo)
        _render_dual_stock_output(df_para_mapear, df_modelo_estoque)
    elif upload.attachments:
        st.warning('Arquivo recebido, mas ainda não encontrei uma tabela válida.')

    df_final = st.session_state.get('df_final_cadastro')
    mapping = st.session_state.get('mapping_cadastro', {})
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final do cadastro', df_final)
        download_final(df_final, 'cadastro', 'cadastro')
