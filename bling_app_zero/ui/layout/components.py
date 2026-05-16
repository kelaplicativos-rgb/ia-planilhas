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
    """Hero principal renderizado em um unico bloco HTML.

    Evita o efeito quebrado no mobile causado por abrir/fechar divs em
    chamadas separadas do Streamlit.
    """
    st.markdown(
        """
        <section class="bling-hero" aria-label="MapeiaPlan.AI">
            <div class="bling-hero-kicker">Mapeamento inteligente de planilhas</div>
            <h1 class="bling-hero-title">MapeiaPlan.AI</h1>
            <p class="bling-hero-subtitle">Transforme qualquer origem em uma planilha pronta no modelo certo.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


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
