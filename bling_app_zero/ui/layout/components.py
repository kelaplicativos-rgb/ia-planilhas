from __future__ import annotations

import html

import streamlit as st


def inject_clean_home_css() -> None:
    """Compatibilidade visual.

    O layout global agora e comandado por bling_app_zero.ui.layout.theme.
    Mantemos esta funcao para telas antigas que ainda a chamam, mas sem criar
    um segundo CSS concorrente.
    """
    from bling_app_zero.ui.layout.theme import inject_app_layout

    inject_app_layout()


def render_compact_hero() -> None:
    from bling_app_zero.core.debug import render_debug_compact_button

    outer_l, outer_c, outer_r = st.columns([0.06, 0.88, 0.06])
    with outer_c:
        st.markdown('<div class="bling-hero">', unsafe_allow_html=True)
        left, center, right = st.columns([0.12, 0.76, 0.12])
        with left:
            st.empty()
        with center:
            st.markdown('<div class="bling-hero-title">🚀 IA Planilhas → Bling</div>', unsafe_allow_html=True)
            st.markdown(
                '<p class="bling-hero-subtitle">Sistema inteligente para transformar dados em CSV pronto para o Bling, com fluxo limpo, leve e organizado.</p>',
                unsafe_allow_html=True,
            )
        with right:
            st.markdown('<div class="bling-tech-button-slot">', unsafe_allow_html=True)
            render_debug_compact_button()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


def render_home_start_card() -> None:
    st.markdown('<div class="bling-home-button-center"></div>', unsafe_allow_html=True)


def render_home_pricing_card() -> None:
    return None


def close_home_start_card() -> None:
    return None


def render_step_title(title: str, caption: str | None = None) -> None:
    safe_title = html.escape(str(title or ''))
    st.markdown(f'<div class="bling-step-title">{safe_title}</div>', unsafe_allow_html=True)
    if caption:
        safe_caption = html.escape(str(caption or ''))
        st.markdown(f'<div class="bling-muted">{safe_caption}</div>', unsafe_allow_html=True)


def render_compact_note(text: str) -> None:
    safe_text = html.escape(str(text or ''))
    st.markdown(f'<div class="bling-compact-note">{safe_text}</div>', unsafe_allow_html=True)


__all__ = [
    'inject_clean_home_css',
    'render_compact_hero',
    'render_home_start_card',
    'render_home_pricing_card',
    'close_home_start_card',
    'render_step_title',
    'render_compact_note',
]
