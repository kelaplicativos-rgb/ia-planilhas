from __future__ import annotations

import hashlib

import pandas as pd
import streamlit as st

from bling_app_zero.core.ai_mapping_assistant import ai_mapping_enabled, apply_ai_mapping_assist, merge_ai_suggestions
from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping
from bling_app_zero.core.mapping_confidence import confidence_for_mapping, resolved_empty_confidence, sort_targets_by_confidence
from bling_app_zero.core.mapping_super_assistant import safe_default_for_target, super_auto_map_columns
from bling_app_zero.core.text import normalize_key
from bling_app_zero.engines.cadastro_engine import default_model
from bling_app_zero.flows.estoque_contract import default_model as estoque_default_model
from bling_app_zero.ui.home_shared import df_signature, download_final, preview_df, show_mapping
from bling_app_zero.ui.layout import inject_mapping_css, render_mapping_preview, render_mapping_title

EMPTY_CHOOSE_OPTION = '— escolher coluna —'
MANUAL_WRITE_OPTION = '— escrever valor fixo —'
EMPTY_LEAVE_OPTION = '— deixar vazio —'
MANUAL_MAPPING_VALUE = '__BLING_MANUAL_FIXED_VALUE__'
PRICE_TARGET_ALIASES = ['Preço de venda', 'Preço unitário (OBRIGATÓRIO)', 'Preço unitário', 'Preço', 'Valor']
CADASTRO_MAPPING_CONFIRMED_KEY = 'cadastro_mapping_confirmed'
CADASTRO_MAPPING_SIGNATURE_KEY = 'cadastro_mapping_confirmed_signature'
MAPPING_WIDGET_PREFIXES = (
    'cad_map_',
    'stk_map_',
    'cadastro_manual_mapping_',
    'estoque_manual_mapping_from_cadastro_',
)


def _short_hash(value: str, size: int = 12) -> str:
    return hashlib.sha1(str(value or '').encode('utf-8', errors='ignore')).hexdigest()[:size]


def _mapping_base(prefix: str, signature: str) -> str:
    return f'{prefix}{_short_hash(signature)}'


def _target_widget_key(mapping_key: str, target_index: int) -> str:
    return f'{mapping_key}_f{target_index:03d}'


def _manual_value_key(widget_key: str) -> str:
    return f'{widget_key}__manual_value'


def _is_manual_value(value: str | None) -> bool:
    return str(value or '').strip() == MANUAL_MAPPING_VALUE


def _option_value(value: str | None) -> str:
    text = str(value or '').strip()
    if text in {EMPTY_CHOOSE_OPTION, EMPTY_LEAVE_OPTION, MANUAL_WRITE_OPTION, MANUAL_MAPPING_VALUE}:
        return ''
    return text


def _display_option(value: str | None) -> str:
    text = str(value or '').strip()
    if _is_manual_value(text):
        return MANUAL_WRITE_OPTION
    return text if text else EMPTY_LEAVE_OPTION


def _is_explicit_empty(widget_key: str, value: str | None) -> bool:
    return str(value or '').strip() == EMPTY_LEAVE_OPTION or bool(st.session_state.get(f'{widget_key}__empty_resolved'))


def _is_explicit_manual(widget_key: str, value: str | None) -> bool:
    return str(value or '').strip() == MANUAL_WRITE_OPTION or bool(st.session_state.get(f'{widget_key}__manual_resolved')) or _is_manual_value(value)


def _manual_confidence() -> dict[str, object]:
    return {'level': 'verde', 'emoji': '🟢', 'label': 'valor fixo', 'score': 100, 'order': 2}


def _confidence_for_selection(df_source: pd.DataFrame, target: str, selected: str, widget_key: str) -> dict[str, object]:
    if _is_explicit_manual(widget_key, selected):
        return _manual_confidence()
    if _is_explicit_empty(widget_key, selected):
        return resolved_empty_confidence()
    return confidence_for_mapping(df_source, target, _option_value(selected))


def _cadastro_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return df_modelo
    return default_model()


def _estoque_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return df_modelo
    return estoque_default_model()


def _default_index(options: list[str], value: str, widget_key: str | None = None) -> int:
    if widget_key and st.session_state.get(f'{widget_key}__manual_resolved'):
        return options.index(MANUAL_WRITE_OPTION) if MANUAL_WRITE_OPTION in options else 0
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


def _signal_label(target: str, info: dict[str, object]) -> str:
    emoji = str(info.get('emoji') or '🔴')
    return f'{emoji} {target}'


def _ordered_targets_once(order_key: str, target_columns: list[str], confidence: dict[str, dict[str, object]]) -> list[str]:
    saved = st.session_state.get(order_key)
    valid_targets = [str(target) for target in target_columns]
    valid_set = set(valid_targets)
    if isinstance(saved, list):
        clean_saved = [str(item) for item in saved if str(item) in valid_set]
        missing = [target for target in valid_targets if target not in set(clean_saved)]
        if clean_saved or missing:
            order = clean_saved + missing
            st.session_state[order_key] = order
            return order
    order = sort_targets_by_confidence(valid_targets, confidence)
    st.session_state[order_key] = order
    return order


def _required_targets(target_columns: list[str]) -> set[str]:
    return {field.original for field in build_contract(target_columns) if field.required}


def _filter_targets(
    mapping_key: str,
    ordered_targets: list[str],
    confidence: dict[str, dict[str, object]],
    required_targets: set[str],
) -> list[str]:
    levels = {target: str(confidence.get(target, {}).get('level') or '') for target in ordered_targets}
    problem_targets = [target for target in ordered_targets if levels.get(target) in {'vermelho', 'amarelo'}]
    required = [target for target in ordered_targets if target in required_targets]

    col_filter, col_search = st.columns([1, 1])
    with col_filter:
        mode = st.radio(
            'Visualização do mapeamento',
            ['Correções necessárias', 'Obrigatórios', 'Todos os campos'],
            horizontal=True,
            key=f'{mapping_key}_view_mode',
        )
    with col_search:
        search = st.text_input(
            'Buscar campo do Bling',
            value='',
            key=f'{mapping_key}_search',
            placeholder='Ex: preço, fornecedor, GTIN, imagem...',
        )

    if mode == 'Obrigatórios':
        selected = required
    elif mode == 'Todos os campos':
        selected = ordered_targets
    else:
        selected = problem_targets or required

    search_key = normalize_key(search)
    if search_key:
        selected = [target for target in ordered_targets if search_key in normalize_key(target)]

    st.caption(
        f'Mostrando {len(selected)} de {len(ordered_targets)} campo(s). '
        'Campos verdes ficam salvos e não precisam aparecer o tempo todo.'
    )
    return selected


def _clear_stale_mapping_widgets(active_mapping_key: str) -> None:
    """Remove widgets antigos que causam erro frontend em trocas de origem/modelo."""
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith(MAPPING_WIDGET_PREFIXES) and not text.startswith(active_mapping_key):
            st.session_state.pop(text, None)


def _clear_mapping_widgets(mapping_key: str) -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith(f'{mapping_key}_'):
            st.session_state.pop(key, None)


def _current_confidence_from_widgets(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for index, target in enumerate(target_columns):
        widget_key = _target_widget_key(mapping_key, index)
        selected = st.session_state.get(widget_key, current_mapping.get(target, ''))
        result[target] = _confidence_for_selection(df_source, target, selected, widget_key)
    return result


def _manual_values_for_signature(mapping: dict[str, str], target_columns: list[str], mapping_key: str) -> list[str]:
    parts: list[str] = []
    for index, target in enumerate(target_columns):
        if _is_manual_value(mapping.get(target, '')):
            widget_key = _target_widget_key(mapping_key, index)
            parts.append(f'{target}:{st.session_state.get(_manual_value_key(widget_key), "")}')
    return parts


def _mapping_signature(mapping: dict[str, str], df_final: pd.DataFrame, target_columns: list[str] | None = None, mapping_key: str = '') -> str:
    parts = [f'{key}={mapping.get(key, "")}' for key in sorted(mapping)]
    if target_columns and mapping_key:
        parts.extend(_manual_values_for_signature(mapping, target_columns, mapping_key))
    return _short_hash('|'.join(parts) + ':' + df_signature(df_final), size=16)


def _invalidate_confirmation_if_changed(mapping: dict[str, str], df_final: pd.DataFrame, target_columns: list[str], mapping_key: str) -> str:
    signature = _mapping_signature(mapping, df_final, target_columns, mapping_key)
    confirmed_signature = st.session_state.get(CADASTRO_MAPPING_SIGNATURE_KEY)
    if confirmed_signature and confirmed_signature != signature:
        st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
        st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    return signature


def _render_confirm_mapping_button(mapping: dict[str, str], df_final: pd.DataFrame, mapping_key: str, target_columns: list[str]) -> None:
    signature = _invalidate_confirmation_if_changed(mapping, df_final, target_columns, mapping_key)
    confirmed = bool(st.session_state.get(CADASTRO_MAPPING_CONFIRMED_KEY)) and st.session_state.get(CADASTRO_MAPPING_SIGNATURE_KEY) == signature
    if confirmed:
        st.success('Mapeamento confirmado. Você já pode continuar para o preview final.')
        return
    st.info('Revise os campos necessários e clique em Confirmar mapeamento para liberar o Preview.')
    if st.button('Confirmar mapeamento', use_container_width=True, key=f'{mapping_key}_confirm'):
        st.session_state[CADASTRO_MAPPING_CONFIRMED_KEY] = True
        st.session_state[CADASTRO_MAPPING_SIGNATURE_KEY] = signature
        st.success('Mapeamento confirmado.')
        st.rerun()


def _force_price_suggestion(target: str, source_columns: list[str], suggested: str) -> str:
    if target in PRICE_TARGET_ALIASES and 'Preço de venda' in source_columns:
        return 'Preço de venda'
    return suggested


def _build_super_mapping(df_source: pd.DataFrame, model: pd.DataFrame, source_columns: list[str]) -> dict[str, str]:
    auto_mapping = super_auto_map_columns(df_source, model)
    for target, selected in list(auto_mapping.items()):
        default_value = safe_default_for_target(target)
        if default_value:
            auto_mapping[target] = ''
            continue
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


def _apply_safe_defaults(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in out.columns:
        default_value = safe_default_for_target(str(column))
        if default_value:
            out[column] = out[column].apply(lambda value: default_value if not str(value or '').strip() else value)
    return out


def _apply_manual_fixed_values(df: pd.DataFrame, mapping: dict[str, str], target_columns: list[str], mapping_key: str) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for index, target in enumerate(target_columns):
        if not _is_manual_value(mapping.get(target, '')) or target not in out.columns:
            continue
        widget_key = _target_widget_key(mapping_key, index)
        manual_value = str(st.session_state.get(_manual_value_key(widget_key), '') or '')
        out[target] = manual_value
    return out


def _apply_ai_to_session_mapping(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
) -> None:
    result = apply_ai_mapping_assist(df_source, target_columns, current_mapping, only_uncertain=True)
    if not result.enabled:
        st.warning('Assistência com IA não configurada. Para usar, adicione OPENAI_API_KEY nos secrets do Streamlit.')
        return
    if result.applied <= 0:
        st.info('A IA não encontrou ajustes seguros para aplicar agora.')
        return
    st.session_state[mapping_key] = merge_ai_suggestions(current_mapping, result)
    st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
    st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    _clear_mapping_widgets(mapping_key)
    st.session_state.pop(f'{mapping_key}_order', None)
    st.success(f'IA ajustou {result.applied} campo(s) com segurança.')
    st.rerun()


def _render_ai_button(df_source: pd.DataFrame, target_columns: list[str], current_mapping: dict[str, str], mapping_key: str, label: str) -> None:
    if not ai_mapping_enabled():
        st.caption('IA opcional inativa. Configure OPENAI_API_KEY para receber ajuda nos campos em dúvida.')
        return
    if st.button(label, use_container_width=True, key=f'{mapping_key}_ai'):
        _apply_ai_to_session_mapping(df_source, target_columns, current_mapping, mapping_key)


def _render_manual_value_input(target: str, widget_key: str) -> str:
    value_key = _manual_value_key(widget_key)
    manual_value = st.text_input(
        f'Valor fixo para {target}',
        value=str(st.session_state.get(value_key, '') or ''),
        key=value_key,
        placeholder='Digite o valor que será repetido no arquivo final',
    )
    st.caption('Valor fixo: será aplicado em todas as linhas desta coluna no preview e no download final.')
    return str(manual_value or '')


def _render_mapping_select(
    df_source: pd.DataFrame,
    target: str,
    target_index: int,
    suggested: str,
    mapping_key: str,
    options: list[str],
) -> tuple[str, dict[str, object]]:
    widget_key = _target_widget_key(mapping_key, target_index)
    if widget_key in st.session_state:
        widget_value = st.session_state.get(widget_key, suggested)
        suggested = MANUAL_MAPPING_VALUE if widget_value == MANUAL_WRITE_OPTION else _option_value(widget_value)
    raw_before = st.session_state.get(widget_key, suggested)
    info_before = _confidence_for_selection(df_source, target, raw_before, widget_key)
    label = _signal_label(target, info_before)
    default_value = safe_default_for_target(target)
    with st.container(border=True):
        render_mapping_title(label)
        if default_value:
            st.text_input(target, value=default_value, disabled=True, key=f'{widget_key}_default', label_visibility='collapsed')
            selected = ''
            info_after = {'level': 'verde', 'emoji': '🟢', 'label': 'padrão seguro', 'score': 100, 'order': 2}
        else:
            selected_raw = st.selectbox(
                target,
                options,
                index=_default_index(options, suggested, widget_key),
                key=widget_key,
                label_visibility='collapsed',
            )
            if selected_raw == MANUAL_WRITE_OPTION:
                st.session_state[f'{widget_key}__manual_resolved'] = True
                st.session_state.pop(f'{widget_key}__empty_resolved', None)
                _render_manual_value_input(target, widget_key)
                selected = MANUAL_MAPPING_VALUE
            elif selected_raw == EMPTY_LEAVE_OPTION:
                st.session_state[f'{widget_key}__empty_resolved'] = True
                st.session_state.pop(f'{widget_key}__manual_resolved', None)
                selected = ''
            else:
                st.session_state.pop(f'{widget_key}__empty_resolved', None)
                st.session_state.pop(f'{widget_key}__manual_resolved', None)
                selected = _option_value(selected_raw)
            info_after = _confidence_for_selection(df_source, target, selected_raw, widget_key)
            if selected == MANUAL_MAPPING_VALUE:
                info_after = _manual_confidence()
            else:
                _render_mapping_preview(df_source, selected)
    return selected, info_after


def render_manual_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    inject_mapping_css()
    model = _cadastro_model(df_modelo)
    source_columns = [str(column) for column in df_source.columns]
    target_columns = [str(column) for column in model.columns]
    options = [MANUAL_WRITE_OPTION, EMPTY_LEAVE_OPTION] + source_columns
    signature = df_signature(df_source) + ':' + '|'.join(target_columns)
    mapping_key = _mapping_base('cad_map_', signature)
    order_key = f'{mapping_key}_order'
    _clear_stale_mapping_widgets(mapping_key)
    if mapping_key not in st.session_state:
        st.session_state[mapping_key] = _build_super_mapping(df_source, model, source_columns)
        st.session_state.pop(order_key, None)
        st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
        st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    st.markdown('#### 2. Conferir campos do cadastro')
    st.caption('🔴 precisa escolher · 🟡 conferir · 🟢 pronto, valor fixo ou vazio confirmado')
    with st.expander('Ver origem antes de preencher', expanded=False):
        preview_df('Origem para conferir', df_source)
    current_mapping = dict(st.session_state.get(mapping_key, {}))
    _render_ai_button(df_source, target_columns, current_mapping, mapping_key, 'Pedir ajuda da IA nos campos em dúvida')
    current_confidence = _current_confidence_from_widgets(df_source, target_columns, current_mapping, mapping_key)
    ordered_targets = _ordered_targets_once(order_key, target_columns, current_confidence)
    required_targets = _required_targets(target_columns)
    visible_targets = _filter_targets(mapping_key, ordered_targets, current_confidence, required_targets)
    target_index_by_name = {target: index for index, target in enumerate(target_columns)}
    edited_mapping: dict[str, str] = {target: current_mapping.get(target, '') for target in target_columns}
    edited_confidence: dict[str, dict[str, object]] = current_confidence.copy()
    for target in visible_targets:
        target_index = target_index_by_name.get(target, len(edited_mapping))
        selected, info_after = _render_mapping_select(df_source, target, target_index, current_mapping.get(target, ''), mapping_key, options)
        edited_mapping[target] = selected
        edited_confidence[target] = info_after
    st.session_state[mapping_key] = edited_mapping
    st.session_state['mapping_confidence_cadastro'] = edited_confidence
    mapping_for_apply = {target: value for target, value in edited_mapping.items() if not _is_manual_value(value)}
    df_preview_manual = apply_mapping(df_source, model, mapping_for_apply)
    df_preview_manual = _apply_manual_fixed_values(df_preview_manual, edited_mapping, target_columns, mapping_key)
    df_preview_manual = _apply_safe_defaults(df_preview_manual)
    df_preview_manual = sanitize_for_bling(df_preview_manual)
    st.session_state['df_final_cadastro'] = df_preview_manual
    st.session_state['mapping_cadastro'] = edited_mapping
    used_values = [value for value in edited_mapping.values() if value and not _is_manual_value(value)]
    duplicated = sorted({value for value in used_values if used_values.count(value) > 1})
    if duplicated:
        st.warning('A mesma coluna da origem foi usada em mais de um campo: ' + ', '.join(duplicated))
    _render_confirm_mapping_button(edited_mapping, df_preview_manual, mapping_key, target_columns)
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Atualizar prévia do cadastro', use_container_width=True, key=f'{mapping_key}_refresh'):
            st.rerun()
    with col_b:
        if st.button('Refazer sugestões automáticas', use_container_width=True, key=f'{mapping_key}_reset'):
            st.session_state[mapping_key] = _build_super_mapping(df_source, model, source_columns)
            st.session_state.pop('df_final_cadastro', None)
            st.session_state.pop('mapping_cadastro', None)
            st.session_state.pop('mapping_confidence_cadastro', None)
            st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
            st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
            st.session_state.pop(order_key, None)
            _clear_mapping_widgets(mapping_key)
            st.rerun()


def render_manual_stock_mapping(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None, deposito: str) -> None:
    inject_mapping_css()
    model = _estoque_model(df_modelo_estoque)
    source_columns = [str(column) for column in df_source.columns]
    target_columns = [str(column) for column in model.columns]
    options = [MANUAL_WRITE_OPTION, EMPTY_LEAVE_OPTION] + source_columns
    signature = df_signature(df_source) + ':' + '|'.join(target_columns) + f':{deposito}'
    mapping_key = _mapping_base('stk_map_', signature)
    order_key = f'{mapping_key}_order'
    _clear_stale_mapping_widgets(mapping_key)
    if mapping_key not in st.session_state:
        auto_mapping = super_auto_map_columns(df_source, model)
        for target in target_columns:
            if 'deposito' in normalize_key(target):
                auto_mapping[target] = ''
        st.session_state[mapping_key] = auto_mapping
        st.session_state.pop(order_key, None)
    st.markdown('##### Conferir campos do estoque')
    st.caption('🔴 precisa escolher · 🟡 conferir · 🟢 pronto, valor fixo ou vazio confirmado')
    with st.expander('Ver origem do estoque', expanded=False):
        preview_df('Origem para estoque', df_source)
    current_mapping = dict(st.session_state.get(mapping_key, {}))
    _render_ai_button(df_source, target_columns, current_mapping, mapping_key, 'Pedir ajuda da IA no estoque')
    current_confidence = _current_confidence_from_widgets(df_source, target_columns, current_mapping, mapping_key)
    ordered_targets = _ordered_targets_once(order_key, target_columns, current_confidence)
    required_targets = _required_targets(target_columns)
    visible_targets = _filter_targets(mapping_key, ordered_targets, current_confidence, required_targets)
    target_index_by_name = {target: index for index, target in enumerate(target_columns)}
    edited_mapping: dict[str, str] = {target: current_mapping.get(target, '') for target in target_columns}
    edited_confidence: dict[str, dict[str, object]] = current_confidence.copy()
    for target in visible_targets:
        target_index = target_index_by_name.get(target, len(edited_mapping))
        target_key = normalize_key(target)
        widget_key = _target_widget_key(mapping_key, target_index)
        if 'deposito' in target_key:
            with st.container(border=True):
                render_mapping_title('🟢 ' + target)
                st.text_input(target, value=deposito, disabled=True, key=f'{widget_key}_dep', label_visibility='collapsed')
            edited_mapping[target] = ''
            edited_confidence[target] = {'level': 'verde', 'emoji': '🟢', 'label': 'pronto', 'score': 100, 'order': 2}
            continue
        selected, info_after = _render_mapping_select(df_source, target, target_index, current_mapping.get(target, ''), mapping_key, options)
        edited_mapping[target] = selected
        edited_confidence[target] = info_after
    st.session_state[mapping_key] = edited_mapping
    st.session_state['mapping_confidence_estoque_from_cadastro'] = edited_confidence
    mapping_for_apply = {target: value for target, value in edited_mapping.items() if not _is_manual_value(value)}
    df_preview_manual = apply_mapping(df_source, model, mapping_for_apply)
    df_preview_manual = _apply_manual_fixed_values(df_preview_manual, edited_mapping, target_columns, mapping_key)
    df_preview_manual = _fill_deposito_manual(df_preview_manual, deposito)
    df_preview_manual = sanitize_for_bling(df_preview_manual)
    st.session_state['df_final_estoque_from_cadastro'] = df_preview_manual
    st.session_state['mapping_estoque_from_cadastro'] = edited_mapping
    used_values = [value for value in edited_mapping.values() if value and not _is_manual_value(value)]
    duplicated = sorted({value for value in used_values if used_values.count(value) > 1})
    if duplicated:
        st.warning('A mesma coluna da origem foi usada mais de uma vez no estoque: ' + ', '.join(duplicated))
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Atualizar prévia do estoque', use_container_width=True, key=f'{mapping_key}_refresh'):
            st.rerun()
    with col_b:
        if st.button('Refazer sugestões do estoque', use_container_width=True, key=f'{mapping_key}_reset'):
            st.session_state.pop(mapping_key, None)
            st.session_state.pop('df_final_estoque_from_cadastro', None)
            st.session_state.pop('mapping_estoque_from_cadastro', None)
            st.session_state.pop('mapping_confidence_estoque_from_cadastro', None)
            st.session_state.pop(order_key, None)
            _clear_mapping_widgets(mapping_key)
            st.rerun()


def render_dual_stock_output(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None) -> None:
    st.markdown('#### Estoque')
    if not isinstance(df_modelo_estoque, pd.DataFrame) or not len(df_modelo_estoque.columns):
        st.info('Envie o modelo de estoque no passo inicial para gerar também o CSV de estoque.')
        st.session_state.pop('df_final_estoque_from_cadastro', None)
        st.session_state.pop('mapping_estoque_from_cadastro', None)
        return
    st.success('Modelo de estoque encontrado. Você também pode gerar o CSV de estoque com esta mesma origem.')
    deposito = st.text_input('Depósito', value='Não definido', key='cadastro_deposito_estoque_mesma_origem')
    render_manual_stock_mapping(df_source, df_modelo_estoque, deposito)
    mapping_estoque = st.session_state.get('mapping_estoque_from_cadastro', {})
    df_final_estoque = st.session_state.get('df_final_estoque_from_cadastro')
    if isinstance(mapping_estoque, dict):
        show_mapping(mapping_estoque, operation='estoque')
    if isinstance(df_final_estoque, pd.DataFrame):
        preview_df('📦 ESTOQUE · Preview final', df_final_estoque)
        download_final(df_final_estoque, 'estoque', 'estoque_from_cadastro')
