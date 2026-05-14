from __future__ import annotations

import streamlit as st

from bling_app_zero.core.text import normalize_key

FILTER_ALL = 'Todos'
FILTER_RED = 'Pendentes'
FILTER_YELLOW = 'Revisar'
FILTER_GREEN = 'OK'
FILTER_REQUIRED = 'Obrigatórios'


def _normalize_target_list(targets: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for target in targets:
        text = str(target or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _level_for(confidence: dict[str, dict[str, object]], target: str) -> str:
    return str(confidence.get(target, {}).get('level') or '').strip().lower()


def _short_summary(*, selected: int, total: int, red: int, yellow: int, green: int, required: int) -> str:
    return f'{selected}/{total} campos · Pendentes {red} · Revisar {yellow} · OK {green} · Obrigatórios {required}'


def filter_targets(
    mapping_key: str,
    ordered_targets: list[str],
    confidence: dict[str, dict[str, object]],
    required_targets: set[str],
    sidebar_rule_targets: set[str] | None = None,
) -> list[str]:
    # As regras internas continuam existindo no fluxo, mas não aparecem no mapeamento.
    # Mapeamento deve mostrar apenas o que o usuário precisa escolher/conferir.
    del sidebar_rule_targets

    ordered_targets = _normalize_target_list(ordered_targets)
    required_targets = {str(target).strip() for target in required_targets if str(target).strip()}

    red_targets = [target for target in ordered_targets if _level_for(confidence, target) == 'vermelho']
    yellow_targets = [target for target in ordered_targets if _level_for(confidence, target) == 'amarelo']
    green_targets = [target for target in ordered_targets if _level_for(confidence, target) == 'verde']
    required = [target for target in ordered_targets if target in required_targets]

    mode_options = [FILTER_ALL, FILTER_RED, FILTER_YELLOW, FILTER_GREEN, FILTER_REQUIRED]

    with st.container(border=True):
        st.caption('Filtrar campos')
        col_mode, col_search = st.columns([0.44, 0.56])
        with col_mode:
            mode = st.selectbox(
                'Filtrar campos',
                mode_options,
                index=0,
                key=f'{mapping_key}_view_mode',
                label_visibility='collapsed',
            )
        with col_search:
            search = st.text_input(
                'Buscar campo',
                value='',
                key=f'{mapping_key}_search',
                placeholder='Buscar campo...',
                label_visibility='collapsed',
            )

    if mode == FILTER_RED:
        selected = red_targets
    elif mode == FILTER_YELLOW:
        selected = yellow_targets
    elif mode == FILTER_GREEN:
        selected = green_targets
    elif mode == FILTER_REQUIRED:
        selected = required
    else:
        selected = ordered_targets

    search_key = normalize_key(search)
    if search_key:
        selected = [target for target in selected if search_key in normalize_key(target)]

    st.caption(
        _short_summary(
            selected=len(selected),
            total=len(ordered_targets),
            red=len(red_targets),
            yellow=len(yellow_targets),
            green=len(green_targets),
            required=len(required),
        )
    )
    return selected


__all__ = ['filter_targets']
