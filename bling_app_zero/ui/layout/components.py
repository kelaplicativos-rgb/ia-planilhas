from __future__ import annotations

import html

import streamlit as st


def inject_clean_home_css() -> None:
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
            overflow-x: hidden !important;
            max-width: 100vw !important;
        }

        .main .block-container,
        .block-container {
            max-width: 980px !important;
            padding-top: 0.75rem !important;
            padding-bottom: 1.5rem !important;
            overflow-x: hidden !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.48rem !important;
        }

        div[data-testid="column"],
        div[data-testid="stElementContainer"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }

        .bling-hero-title {
            font-size: clamp(1.25rem, 4vw, 1.85rem);
            line-height: 1.20;
            font-weight: 900;
            text-align: center;
            margin: 0 0 0.35rem 0;
            color: rgba(17, 24, 39, 0.96);
        }

        .bling-hero-subtitle {
            font-size: clamp(0.84rem, 2.4vw, 0.98rem);
            line-height: 1.38;
            color: rgba(49, 51, 63, 0.68);
            text-align: center;
            margin: 0;
        }

        .bling-tech-button-slot .stButton > button {
            min-height: 30px !important;
            height: 30px !important;
            width: 30px !important;
            border-radius: 999px !important;
            padding: 0 !important;
            font-size: 0.80rem !important;
            opacity: 0.74;
            border: 1px solid rgba(15, 23, 42, 0.13) !important;
            background: rgba(255, 255, 255, 0.96) !important;
            color: rgba(17, 24, 39, 0.78) !important;
            box-shadow: 0 4px 10px rgba(15, 23, 42, 0.06) !important;
        }

        .bling-tech-button-slot .stButton > button:hover {
            opacity: 1;
            border-color: rgba(185, 28, 28, 0.30) !important;
        }

        .bling-home-button-center {
            width: min(100%, 310px);
            margin: 0.95rem auto 0 auto;
        }

        .bling-step-title {
            font-size: 1.14rem;
            line-height: 1.28;
            font-weight: 850;
            margin: 0.65rem 0 0.25rem 0;
            color: rgba(17, 24, 39, 0.96);
        }

        .bling-muted {
            color: rgba(49, 51, 63, 0.68);
            font-size: 0.92rem;
            line-height: 1.42;
            margin: 0 0 0.62rem 0;
        }

        .bling-compact-note {
            border-radius: 12px;
            padding: 9px 11px;
            background: rgba(240, 242, 246, 0.72);
            color: rgba(49, 51, 63, 0.76);
            font-size: 0.88rem;
            line-height: 1.38;
            margin: 7px 0 10px 0;
        }

        button[kind="primary"] {
            background: linear-gradient(135deg, #b91c1c, #ef4444) !important;
            color: #ffffff !important;
            border: 0 !important;
            box-shadow: 0 14px 30px rgba(185, 28, 28, 0.24) !important;
        }

        button[kind="primary"]:active,
        button[kind="primary"]:focus:not(:active) {
            background: #991b1b !important;
            color: #ffffff !important;
            box-shadow: 0 10px 22px rgba(185, 28, 28, 0.30) !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 14px !important;
            min-height: 44px;
            padding: 0.48rem 0.72rem;
            font-size: 0.95rem;
            line-height: 1.24;
            white-space: normal;
        }

        div[data-testid="stFileUploader"] section {
            padding: 10px 12px !important;
            min-height: 78px !important;
            border-radius: 14px !important;
        }

        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                padding-left: 0.78rem !important;
                padding-right: 0.78rem !important;
                padding-top: 0.72rem !important;
            }

            header[data-testid="stHeader"] {
                visibility: visible !important;
                height: 2.70rem !important;
                min-height: 2.70rem !important;
                background: rgba(255,255,255,0.78) !important;
                backdrop-filter: blur(10px);
            }

            .bling-hero-title {
                font-size: 1.12rem;
            }

            .bling-hero-subtitle {
                font-size: 0.80rem;
            }

            .bling-home-button-center {
                width: min(100%, 285px);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_compact_hero() -> None:
    from bling_app_zero.core.debug import render_debug_compact_button

    with st.container(border=True):
        left, center, right = st.columns([0.08, 0.84, 0.08], vertical_alignment='top')
        with left:
            st.empty()
        with center:
            st.markdown('<div class="bling-hero-title">🚀 IA Planilhas → Bling</div>', unsafe_allow_html=True)
            st.markdown('<p class="bling-hero-subtitle">Transforme dados em CSV pronto para o Bling.</p>', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="bling-tech-button-slot">', unsafe_allow_html=True)
            render_debug_compact_button()
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
