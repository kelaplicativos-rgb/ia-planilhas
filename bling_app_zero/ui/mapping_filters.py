from __future__ import annotations

import streamlit as st

from bling_app_zero.core.text import normalize_key
from bling_app_zero.ui.mapping_sidebar_rule_badge import SIDEBAR_RULE_FILTER_LABEL, filter_sidebar_rule_targets, sidebar_rule_count

FILTER_ALL = 'Todos'
FILTER_RED = 'Pendentes'
FILTER_YELLOW = 'Conferir'
FILTER_GREEN = 'Prontos'
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


def _short_summary(*, selected: int, total: int, red: int, yellow: int, green: int, purple: int, required: int) -> str:
    return f'{selected}/{total} campos · 🔴 {red} · 🟡 {yellow} · 🟢 {green} · 🟣 {purple} · Obrig. {required}'


def filter_targets(
    mapping_key: str,
    ordered_targets: list[str],
    confidence: dict[str, dict[str, object]],
    required_targets: set[str],
    sidebar_rule_targets: set[str] | None = None,
) -> list[str]:
    sidebar_rule_targets = sidebar_rule_targets or set()
    ordered_targets = _normalize_target_list(ordered_targets)
    required_targets = {str(target).strip() for target in required_targets if str(target).strip()}

    red_targets = [target for target in ordered_targets if _level_for(confidence, target) == 'vermelho']
    yellow_targets = [target for target in ordered_targets if _level_for(confidence, target) == 'amarelo']
    green_targets = [target for target in ordered_targets if _level_for(confidence, target) == 'verde']
    required = [target for target in ordered_targets if target in required_targets]
    sidebar_targets = filter_sidebar_rule_targets(ordered_targets, sidebar_rule_targets)

    mode_options = [FILTER_ALL, FILTER_RED, FILTER_YELLOW, FILTER_GREEN, SIDEBAR_RULE_FILTER_LABEL, FILTER_REQUIRED]

    with st.container(border=True):
        col_mode, col_search = st.columns([0.44, 0.56])
        with col_mode:
            mode = st.selectbox(
                'Ver',
                mode_options,
                index=0,
                key=f'{mapping_key}_view_mode',
                label_visibility='collapsed',
            )
        with col_search:
            search = st.text_input(
                'Buscar',
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
    elif mode == SIDEBAR_RULE_FILTER_LABEL:
        selected = sidebar_targets
    elif mode == FILTER_REQUIRED:
        selected = required
    else:
        selected = ordered_targets

    search_key = normalize_key(search)
    if search_key:
        selected = [target for target in selected if search_key in normalize_key(target)]

    red_count = len(red_targets)
    yellow_count = len(yellow_targets)
    green_count = len(green_targets)
    purple_count = sidebar_rule_count(ordered_targets, sidebar_rule_targets)
    required_count = len(required)

    st.caption(
        _short_summary(
            selected=len(selected),
            total=len(ordered_targets),
            red=red_count,
            yellow=yellow_count,
            green=green_count,
            purple=purple_count,
            required=required_count,
        )
    )
    return selected


__all__ = ['filter_targets']
