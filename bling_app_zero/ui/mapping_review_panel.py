from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def _safe_text(value: object, fallback: str = '') -> str:
    text = str(value if value is not None else '').strip()
    return text if text else fallback


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _confidence_level(info: Any) -> str:
    if isinstance(info, dict):
        return _safe_text(info.get('level')).lower()
    return ''


def _confidence_emoji(level: str) -> str:
    if level == 'verde':
        return '🟢'
    if level == 'amarelo':
        return '🟡'
    return '🔴'


def _source_preview(df_source: pd.DataFrame, source_column: str) -> str:
    source_column = _safe_text(source_column)
    if not source_column or not isinstance(df_source, pd.DataFrame) or source_column not in df_source.columns or df_source.empty:
        return ''
    value = df_source[source_column].iloc[0]
    text = _safe_text(value)
    return text[:120] + '...' if len(text) > 120 else text


def _count_levels(target_columns: list[str], confidence: dict[str, Any]) -> tuple[int, int, int]:
    green = yellow = red = 0
    for target in target_columns:
        level = _confidence_level(confidence.get(target))
        if level == 'verde':
            green += 1
        elif level == 'amarelo':
            yellow += 1
        else:
            red += 1
    return green, yellow, red


def render_mapping_review_panel(
    operation: str,
    mapping: dict[str, str] | None,
    confidence: dict[str, Any] | None,
    df_source: pd.DataFrame | None,
    target_columns: list[str] | None,
) -> None:
    """Mostra uma revisão leve do mapeamento sem depender de IA.

    Este módulo existe para evitar quebra no import compartilhado entre cadastro
    e estoque. Ele apenas resume o que já está em session_state e não altera o
    mapeamento final.
    """
    safe_mapping = {str(k): _safe_text(v) for k, v in _as_dict(mapping).items()}
    safe_confidence = _as_dict(confidence)
    columns = [str(column) for column in (target_columns or [])]

    if not columns:
        return

    green, yellow, red = _count_levels(columns, safe_confidence)
    title = 'Revisão do mapeamento'
    if operation:
        title = f'Revisão do mapeamento - {operation}'

    with st.expander(title, expanded=False):
        st.caption(f'Resumo: 🟢 {green} pronto(s) · 🟡 {yellow} conferir · 🔴 {red} pendente(s).')

        rows: list[dict[str, str]] = []
        for target in columns:
            selected = safe_mapping.get(target, '')
            level = _confidence_level(safe_confidence.get(target))
            rows.append(
                {
                    'Status': _confidence_emoji(level),
                    'Campo Bling': target,
                    'Origem/valor': selected if selected else '— vazio —',
                    'Exemplo': _source_preview(df_source, selected) if isinstance(df_source, pd.DataFrame) else '',
                }
            )

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


__all__ = ['render_mapping_review_panel']
