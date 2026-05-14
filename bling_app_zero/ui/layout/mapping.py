from __future__ import annotations

import html

import streamlit as st

from bling_app_zero.ui.mapping_sidebar_rule_badge import with_sidebar_rule_badge


def inject_mapping_css() -> None:
    """Compatibilidade: o mapeamento agora herda somente o tema global da Home.

    BLINGFIX TEMA ÚNICO:
    Não injeta CSS próprio para evitar múltiplos temas concorrendo na mesma tela.
    O visual deve vir de bling_app_zero/ui/layout/theme.py.
    """
    return None


def render_mapping_title(target_label: str) -> None:
    raw = with_sidebar_rule_badge(str(target_label or ''))
    safe = html.escape(raw)
    st.markdown(f'<div class="bling-map-title"><span class="bling-map-title-text">{safe}</span></div>', unsafe_allow_html=True)


def render_mapping_preview(text: str) -> None:
    safe = html.escape(str(text or '').strip())
    if not safe:
        return
    st.markdown(f'<div class="bling-map-preview">{safe}</div>', unsafe_allow_html=True)


__all__ = ['inject_mapping_css', 'render_mapping_title', 'render_mapping_preview']
