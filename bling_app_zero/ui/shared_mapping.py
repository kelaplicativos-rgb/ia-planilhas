from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_openai_mapping_suggester import suggest_mapping_with_openai
from bling_app_zero.ui.mapping_cadastro_flow import render_manual_mapping
from bling_app_zero.ui.mapping_estoque_flow import render_manual_stock_mapping
from bling_app_zero.ui.shared_calculator import (
    UNIVERSAL_PRICE_AUTOMAP_KEY,
    UNIVERSAL_PRICE_COLUMN_KEY,
    UNIVERSAL_PRICE_TARGET_COLUMN_KEY,
)

EMPTY_OPTION = '(deixar vazio)'
WRITE_OPTION = '✍️ escrever valor fixo/manual'
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'
MAPPING_FIELDS_PER_PAGE = 10


def render_shared_cadastro_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    render_manual_mapping(df_source, df_modelo)


def render_shared_stock_mapping(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None, deposito: str) -> None:
    render_manual_stock_mapping(df_source, df_modelo_estoque, deposito)


def short_hash(value: str, size: int = 8) -> str:
    return hashlib.sha256(str(value or '').encode('utf-8')).hexdigest()[:size]


def mapping_widget_key(key_prefix: str, signature: str, index: int, target_name: str) -> str:
    return f'{key_prefix}_map_{index}_{short_hash(signature + target_name)}'


def fixed_widget_key(key_prefix: str, signature: str, index: int, target_name: str) -> str:
    return f'{mapping_widget_key(key_prefix, signature, index, target_name)}_fixed_value'


def encode_fixed_value(value: object) -> str:
    text = str(value or '').strip()
    return f'{FIXED_VALUE_PREFIX}{text}' if text else ''


def is_fixed_value(value: object) -> bool:
    return str(value or '').startswith(FIXED_VALUE_PREFIX)


def decode_fixed_value(value: object) -> str:
    text = str(value or '')
    if text.startswith(FIXED_VALUE_PREFIX):
        return text[len(FIXED_VALUE_PREFIX):].strip()
    return text.strip()


def _norm(value: object) -> str:
    text = str(value or '').lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '', text)


def _tokens(value: object) -> set[str]:
    text = str(value or '').lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return {part for part in re.split(r'[^a-z0-9]+', text) if part}


def _pct(score: float) -> int:
    return int(round(max(0.0, min(1.0, float(score or 0))) * 100))


def _sample_values(source: pd.DataFrame, source_column: str, limit: int = 3) -> list[str]:
    if not isinstance(source, pd.DataFrame) or not source_column or source_column not in source.columns:
        return []
    values: list[str] = []
    try:
        for value in source[source_column].dropna().astype(str).head(limit * 4):
            text = str(value or '').strip()
            if text and text.lower() not in {'nan', 'none', 'null'} and text not in values:
                values.append(text)
            if len(values) >= limit:
                break
    except Exception:
        return []
    return values


def _short_preview(values: list[str], max_chars: int = 150) -> str:
    text = ' | '.join(values)
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + '…'


def confidence_flag(target: str, source_column: str, source: pd.DataFrame) -> str:
    if is_fixed_value(source_column):
        return '🟢 fixo'
    if not source_column:
        return '🔴 vazio'
    target_key = _norm(target)
    source_key = _norm(source_column)
    if target_key and (target_key == source_key or target_key in source_key or source_key in target_key):
        return '🟢 alto'
    if source_column in source.columns and source[source_column].astype(str).str.strip().ne('').any():
        return '🟡 revisar'
    return '🔴 vazio'


def _confidence_icon(target: str, source_column: str, source: pd.DataFrame) -> str:
    return confidence_flag(target, source_column, source).split()[0]


def _render_mapping_preview(target_name: str, selected_value: str, source: pd.DataFrame) -> None:
    icon = _confidence_icon(target_name, selected_value, source)
    if is_fixed_value(selected_value):
        fixed_value = decode_fixed_value(selected_value)
        st.caption(f'{icon} **{target_name}**. Valor fixo: {fixed_value}' if fixed_value else f'🔴 **{target_name}**. Valor fixo vazio.')
        return
    if not selected_value:
        st.caption(f'{icon} **{target_name}**. Ficará vazio no download final.')
        return
    samples = _sample_values(source, selected_value)
    st.caption(f'{icon} **{target_name}**. Prévia: {_short_preview(samples)}' if samples else f'{icon} **{target_name}**. Prévia indisponível ou coluna vazia.')


def _extract_suggestion_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    suggestions = data.get('suggestions', []) if isinstance(data, dict) else []
    indexed: dict[str, dict[str, Any]] = {}
    if isinstance(suggestions, list):
        for item in suggestions:
            if isinstance(item, dict):
                target = str(item.get('target_column') or '').strip()
                if target and target not in indexed:
                    indexed[target] = dict(item)
    return indexed


def _suggest_shared_mapping_with_metadata(source: pd.DataFrame, target: pd.DataFrame, *, operation: str = 'universal') -> tuple[dict[str, str], str, dict[str, dict[str, Any]]]:
    result = suggest_mapping_with_openai(source, target, operation=operation)
    data = result.data if isinstance(result.data, dict) else {}
    mapping = data.get('mapping')
    engine = str(data.get('engine') or 'local')
    safe_mapping = {str(k): str(v) for k, v in mapping.items()} if isinstance(mapping, dict) else {}
    return safe_mapping, engine, _extract_suggestion_index(data)


def suggest_shared_mapping(source: pd.DataFrame, target: pd.DataFrame, *, operation: str = 'universal') -> tuple[dict[str, str], str]:
    mapping, engine, _metadata = _suggest_shared_mapping_with_metadata(source, target, operation=operation)
    return mapping, engine


def blank_shared_mapping(target: pd.DataFrame) -> dict[str, str]:
    return {str(column): '' for column in getattr(target, 'columns', [])}


def _apply_price_calculator_mapping_hint(current: dict[str, str], source: pd.DataFrame, target: pd.DataFrame) -> dict[str, str]:
    if not bool(st.session_state.get(UNIVERSAL_PRICE_AUTOMAP_KEY)):
        return current
    calculated_source = str(st.session_state.get(UNIVERSAL_PRICE_COLUMN_KEY) or '').strip()
    target_column = str(st.session_state.get(UNIVERSAL_PRICE_TARGET_COLUMN_KEY) or '').strip()
    if not calculated_source or not isinstance(source, pd.DataFrame) or calculated_source not in source.columns:
        return current
    target_columns = [str(column) for column in getattr(target, 'columns', [])]
    if not target_column or target_column not in target_columns:
        calculated_key = _norm(calculated_source)
        target_column = next((column for column in target_columns if _norm(column) == calculated_key), '')
    if not target_column:
        return current
    updated = dict(current or {})
    updated[target_column] = calculated_source
    st.caption(f'🟢 Calculadora marketplace: **{target_column}** receberá automaticamente **{calculated_source}**.')
    return updated


def _score_from_similarity(target_name: str, source_column: str) -> float:
    target_key = _norm(target_name)
    source_key = _norm(source_column)
    if not target_key or not source_key:
        return 0.0
    if target_key == source_key:
        return 1.0
    if target_key in source_key or source_key in target_key:
        return 0.88
    target_tokens = _tokens(target_name)
    source_tokens = _tokens(source_column)
    if target_tokens and source_tokens:
        overlap = len(target_tokens & source_tokens) / max(len(target_tokens), 1)
        if overlap >= 0.75:
            return 0.82
        if overlap >= 0.50:
            return 0.70
    return 0.0


def _metadata_scores(target_name: str, suggestions_index: dict[str, dict[str, Any]]) -> dict[str, float]:
    item = suggestions_index.get(target_name) if isinstance(suggestions_index, dict) else None
    scores: dict[str, float] = {}
    if not isinstance(item, dict):
        return scores
    source = str(item.get('source_column') or '').strip()
    try:
        confidence = float(item.get('confidence') or 0)
    except Exception:
        confidence = 0.0
    if source:
        scores[source] = max(scores.get(source, 0.0), confidence)
    alternatives = item.get('alternatives')
    if isinstance(alternatives, list):
        for alt in alternatives:
            if isinstance(alt, dict):
                alt_source = str(alt.get('source_column') or '').strip()
                if not alt_source:
                    continue
                try:
                    score = float(alt.get('score') or alt.get('confidence') or 0)
                except Exception:
                    score = 0.0
                scores[alt_source] = max(scores.get(alt_source, 0.0), score)
    return scores


def _ranked_source_options(target_name: str, current_value: str, source_columns: list[str], suggestions_index: dict[str, dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
    scores = _metadata_scores(target_name, suggestions_index)
    if current_value in source_columns:
        scores[current_value] = max(scores.get(current_value, 0.0), 0.96)
    for column in source_columns:
        scores[column] = max(scores.get(column, 0.0), _score_from_similarity(target_name, column))
    original_position = {column: pos for pos, column in enumerate(source_columns)}
    ranked_columns = sorted(source_columns, key=lambda column: (-float(scores.get(column, 0.0)), original_position.get(column, 9999), str(column).casefold()))
    confident_columns = [column for column in ranked_columns if float(scores.get(column, 0.0)) >= 0.70]
    other_columns = [column for column in ranked_columns if column not in confident_columns]
    options = confident_columns + [EMPTY_OPTION, WRITE_OPTION] + other_columns if confident_columns else [EMPTY_OPTION, WRITE_OPTION] + other_columns
    labels: dict[str, str] = {EMPTY_OPTION: EMPTY_OPTION, WRITE_OPTION: WRITE_OPTION}
    for column in source_columns:
        percent = _pct(scores.get(column, 0.0))
        if percent >= 99:
            labels[column] = f'🟢 100% recomendado — {column}'
        elif percent >= 95:
            labels[column] = f'🟢 {percent}% recomendado — {column}'
        elif percent >= 90:
            labels[column] = f'🟢 {percent}% alta confiança — {column}'
        elif percent >= 70:
            labels[column] = f'🟡 {percent}% revisar — {column}'
        else:
            labels[column] = f'⚪ {column}'
    return options, labels


def _initial_select_value(current_value: str, source_options: list[str]) -> str:
    if is_fixed_value(current_value):
        return WRITE_OPTION
    if current_value in source_options:
        return current_value
    if current_value:
        return WRITE_OPTION
    return EMPTY_OPTION


def _fixed_initial_value(current_value: str) -> str:
    if is_fixed_value(current_value):
        return decode_fixed_value(current_value)
    if current_value and current_value not in {EMPTY_OPTION, WRITE_OPTION}:
        return str(current_value or '').strip()
    return ''


def _mapping_page_keys(key_prefix: str, signature: str) -> tuple[str, str]:
    suffix = short_hash(signature, size=10)
    return f'{key_prefix}_mapping_page_{suffix}', f'{key_prefix}_mapping_scroll_{suffix}'


def _mapping_search_key(key_prefix: str, signature: str) -> str:
    return f'{key_prefix}_mapping_search_{short_hash(signature, size=10)}'


def _suggestion_state_key(mapping_state_key: str, signature: str) -> str:
    return f'{mapping_state_key}_suggestions_{short_hash(signature, size=10)}'


def _filter_target_columns(target_columns: list[str], query: str) -> list[str]:
    terms = [_norm(part) for part in str(query or '').split() if _norm(part)]
    if not terms:
        return list(target_columns)
    return [column for column in target_columns if all(term in _norm(column) for term in terms)]


def _reset_page_when_search_changes(page_key: str, search_key: str, query: str) -> None:
    previous_key = f'{search_key}_previous_value'
    previous = str(st.session_state.get(previous_key) or '')
    current = str(query or '')
    if previous != current:
        st.session_state[page_key] = 1
        st.session_state[previous_key] = current


def _change_mapping_page(page_key: str, scroll_key: str, page: int) -> None:
    st.session_state[page_key] = max(1, int(page))
    st.session_state[scroll_key] = True
    try:
        st.rerun()
    except Exception:
        pass


def _render_mapping_page_controls(page_key: str, scroll_key: str, current_page: int, total_pages: int, *, where: str) -> None:
    if total_pages <= 1:
        return
    previous_disabled = current_page <= 1
    next_disabled = current_page >= total_pages
    col_prev, col_page, col_next = st.columns([1, 1.2, 1])
    with col_prev:
        if st.button('← Anterior', key=f'{page_key}_{where}_prev', use_container_width=True, disabled=previous_disabled):
            _change_mapping_page(page_key, scroll_key, current_page - 1)
    with col_page:
        selected = st.selectbox('Página', list(range(1, total_pages + 1)), index=max(0, min(total_pages - 1, current_page - 1)), key=f'{page_key}_{where}_select', label_visibility='collapsed')
        if int(selected) != int(current_page):
            _change_mapping_page(page_key, scroll_key, int(selected))
    with col_next:
        if st.button('Próxima →', key=f'{page_key}_{where}_next', use_container_width=True, disabled=next_disabled):
            _change_mapping_page(page_key, scroll_key, current_page + 1)


def render_shared_contract_mapping(source: pd.DataFrame, target: pd.DataFrame, *, signature: str, mapping_state_key: str, engine_state_key: str, key_prefix: str = 'mapeiaai_shared', ai_enabled: bool = True) -> dict[str, str]:
    st.markdown('### Mapeamento')
    page_key, scroll_key = _mapping_page_keys(key_prefix, signature)
    search_key = _mapping_search_key(key_prefix, signature)
    suggestions_key = _suggestion_state_key(mapping_state_key, signature)
    st.session_state.pop(scroll_key, None)

    if ai_enabled:
        st.caption('IA opcional ligada: o sistema sugere os campos, mas você revisa e pode alterar tudo antes do preview final.')

    if mapping_state_key not in st.session_state:
        if ai_enabled:
            suggested, engine, suggestions_index = _suggest_shared_mapping_with_metadata(source, target, operation='universal')
        else:
            suggested, engine, suggestions_index = blank_shared_mapping(target), 'manual_sem_ia', {}
        st.session_state[mapping_state_key] = suggested
        st.session_state[engine_state_key] = engine
        st.session_state[suggestions_key] = suggestions_index

    if not ai_enabled and str(st.session_state.get(engine_state_key) or '') != 'manual_sem_ia':
        st.session_state[mapping_state_key] = blank_shared_mapping(target)
        st.session_state[engine_state_key] = 'manual_sem_ia'
        st.session_state[suggestions_key] = {}

    engine = str(st.session_state.get(engine_state_key) or 'local')
    if engine == 'openai_validated':
        st.caption('Motor de sugestão: OpenAI validada')
    elif engine != 'manual_sem_ia':
        st.caption('Motor de sugestão: local seguro')

    current = dict(st.session_state.get(mapping_state_key) or {})
    current = _apply_price_calculator_mapping_hint(current, source, target)
    st.session_state[mapping_state_key] = current
    suggestions_index = st.session_state.get(suggestions_key)
    suggestions_index = suggestions_index if isinstance(suggestions_index, dict) else {}
    source_columns = [str(column) for column in source.columns]
    edited: dict[str, str] = dict(current)
    rows: list[dict[str, str]] = []

    all_target_columns = [str(column) for column in getattr(target, 'columns', [])]
    search_query = st.text_input('Buscar campo/coluna do modelo', value=str(st.session_state.get(search_key) or ''), key=search_key, placeholder='Ex.: validade, preço, vídeo, estoque', help='Filtra somente os campos do modelo.').strip()
    _reset_page_when_search_changes(page_key, search_key, search_query)
    target_columns = _filter_target_columns(all_target_columns, search_query)

    total_fields = len(target_columns)
    total_pages = max(1, math.ceil(total_fields / MAPPING_FIELDS_PER_PAGE))
    current_page = max(1, min(total_pages, int(st.session_state.get(page_key) or 1)))
    st.session_state[page_key] = current_page
    start = (current_page - 1) * MAPPING_FIELDS_PER_PAGE
    end = min(total_fields, start + MAPPING_FIELDS_PER_PAGE)
    page_columns = target_columns[start:end]
    start_display = start + 1 if total_fields else 0

    if search_query:
        st.caption(f'Filtro ativo: {len(target_columns)} de {len(all_target_columns)} campo(s) encontrado(s).')
    if search_query and not target_columns:
        st.warning('Nenhum campo encontrado para essa busca. Limpe ou altere o texto para voltar aos campos do modelo.')

    st.caption(f'Mostrando campos {start_display}–{end} de {total_fields}. Limite: {MAPPING_FIELDS_PER_PAGE} campos por página para não pesar a tela.')
    st.caption('As melhores sugestões aparecem primeiro no dropdown: 🟢 100%/95%/90%, depois 🟡 revisar e por último as demais colunas.')
    _render_mapping_page_controls(page_key, scroll_key, current_page, total_pages, where='top')

    for offset, target_name in enumerate(page_columns):
        index = all_target_columns.index(target_name) if target_name in all_target_columns else start + offset
        current_value = str(current.get(target_name, '') or '')
        source_options, option_labels = _ranked_source_options(target_name, current_value, source_columns, suggestions_index)
        selected_initial = _initial_select_value(current_value, source_options)
        default_index = source_options.index(selected_initial) if selected_initial in source_options else 0

        with st.container(border=True):
            st.caption(f'Campo {index + 1}: **{target_name}**')
            top_option = next((option for option in source_options if option not in {EMPTY_OPTION, WRITE_OPTION}), '')
            top_label = option_labels.get(top_option, '') if top_option else ''
            if top_label.startswith('🟢'):
                st.caption(f'Melhor sugestão: {top_label}')
            selected = st.selectbox(f'Como preencher “{target_name}”', source_options, index=default_index, key=mapping_widget_key(key_prefix, signature, index, target_name), format_func=lambda option, labels=option_labels: labels.get(str(option), str(option)))

            fixed_value = ''
            if selected == WRITE_OPTION:
                fixed_value = st.text_input(f'Escrever valor para refletir na coluna inteira de “{target_name}”', value=_fixed_initial_value(current_value), key=fixed_widget_key(key_prefix, signature, index, target_name), placeholder='Digite aqui o valor que será repetido nesta coluna.').strip()

            selected_value = encode_fixed_value(fixed_value) if selected == WRITE_OPTION else ('' if selected == EMPTY_OPTION else str(selected))
            edited[target_name] = selected_value
            _render_mapping_preview(target_name, selected_value, source)

    st.session_state[mapping_state_key] = edited

    for target_name in all_target_columns:
        selected_value = str(edited.get(target_name, '') or '')
        display_value = f'FIXO: {decode_fixed_value(selected_value)}' if is_fixed_value(selected_value) else (selected_value or '(vazio)')
        rows.append({'Farol': confidence_flag(target_name, selected_value, source), 'Contrato final': target_name, 'Origem usada': display_value})

    _render_mapping_page_controls(page_key, scroll_key, current_page, total_pages, where='bottom')
    with st.expander('Resumo dos faróis do mapeamento', expanded=False):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=260)
    return edited


def clear_shared_mapping_widgets(key_prefix: str = 'mapeiaai_shared') -> None:
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith(f'{key_prefix}_map_') or text.startswith(f'{key_prefix}_mapping_page_') or text.startswith(f'{key_prefix}_mapping_scroll_') or text.startswith(f'{key_prefix}_mapping_search_'):
            st.session_state.pop(key, None)


__all__ = [
    'EMPTY_OPTION',
    'FIXED_VALUE_PREFIX',
    'MAPPING_FIELDS_PER_PAGE',
    'WRITE_OPTION',
    'blank_shared_mapping',
    'clear_shared_mapping_widgets',
    'confidence_flag',
    'decode_fixed_value',
    'encode_fixed_value',
    'fixed_widget_key',
    'is_fixed_value',
    'mapping_widget_key',
    'render_shared_cadastro_mapping',
    'render_shared_contract_mapping',
    'render_shared_stock_mapping',
    'short_hash',
    'suggest_shared_mapping',
]
