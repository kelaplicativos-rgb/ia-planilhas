from __future__ import annotations

import html

import streamlit as st


def inject_clean_home_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bling-radius: 18px;
            --bling-accent: #2563eb;
            --bling-red: #b91c1c;
            --bling-text: rgba(17, 24, 39, 0.96);
            --bling-muted: rgba(49, 51, 63, 0.68);
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
            overflow-x: hidden !important;
            max-width: 100vw !important;
        }

        .main .block-container,
        .block-container {
            max-width: 980px !important;
            padding-top: 0.72rem !important;
            padding-bottom: 1.5rem !important;
            overflow-x: hidden !important;
        }

        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"],
        div[data-testid="column"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.46rem !important;
        }

        div[data-testid="column"] {
            padding: 0 0.2rem !important;
        }

        .bling-hero,
        .bling-step-title,
        .bling-muted,
        .bling-compact-note {
            box-sizing: border-box !important;
            max-width: 100% !important;
            overflow-wrap: normal !important;
            word-break: normal !important;
        }

        .bling-hero {
            width: min(100%, 820px);
            margin: 0.10rem auto 0.70rem auto;
            border: 1px solid rgba(15, 23, 42, 0.10);
            border-radius: var(--bling-radius);
            padding: 16px 15px 17px 15px;
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,249,251,0.94));
            overflow: hidden;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.045);
        }

        .bling-hero-row {
            display: grid;
            grid-template-columns: 32px minmax(0, 1fr) 32px;
            align-items: center;
            gap: 8px;
        }

        .bling-hero-text {
            text-align: center;
            min-width: 0;
        }

        .bling-hero-title {
            font-size: clamp(1.34rem, 4vw, 2rem);
            line-height: 1.18;
            font-weight: 900;
            margin: 0 0 6px 0;
            letter-spacing: -0.006em;
            color: var(--bling-text);
        }

        .bling-hero-subtitle {
            font-size: clamp(0.90rem, 2.4vw, 1rem);
            line-height: 1.40;
            color: var(--bling-muted);
            margin: 0 auto;
            max-width: 760px;
        }

        .bling-hero-tech-slot {
            display: flex;
            justify-content: flex-end;
            align-items: flex-start;
            align-self: start;
        }

        .bling-hero-tech-slot .stButton > button {
            min-height: 30px !important;
            height: 30px !important;
            width: 30px !important;
            border-radius: 999px !important;
            padding: 0 !important;
            font-size: 0.82rem !important;
            opacity: 0.72;
            border: 1px solid rgba(15,23,42,0.13) !important;
            background: rgba(255,255,255,0.95) !important;
            color: rgba(17,24,39,0.78) !important;
            box-shadow: 0 4px 10px rgba(15,23,42,0.06) !important;
        }

        .bling-hero-tech-slot .stButton > button:hover {
            opacity: 1;
            border-color: rgba(185,28,28,0.30) !important;
        }

        .bling-step-title {
            font-size: 1.14rem;
            line-height: 1.28;
            font-weight: 850;
            margin: 10px 0 5px 0;
            clear: both;
        }

        .bling-muted {
            color: var(--bling-muted);
            font-size: 0.92rem;
            line-height: 1.42;
            margin: 0 0 0.62rem 0;
            clear: both;
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

        .bling-home-button-center {
            width: min(100%, 310px);
            margin: 1.0rem auto 0 auto;
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

        div[data-baseweb="select"] {
            max-width: 100% !important;
            width: 100% !important;
        }

        div[data-baseweb="select"] > div {
            max-width: 100% !important;
            overflow: hidden !important;
            background: #eef2f7 !important;
            border-radius: 14px !important;
        }

        div[data-baseweb="popover"],
        div[data-baseweb="menu"],
        ul[role="listbox"] {
            max-width: calc(100vw - 24px) !important;
            overflow-x: hidden !important;
        }

        ul[role="listbox"] li {
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            word-break: normal !important;
            background: #ffffff !important;
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
            padding: 11px 12px !important;
            min-height: 82px !important;
            border-radius: 14px !important;
        }

        div[data-testid="stFileUploader"] section p {
            font-size: 0.86rem !important;
            line-height: 1.24 !important;
            margin-bottom: 0.15rem !important;
        }

        div[data-testid="stFileUploader"] small {
            font-size: 0.74rem !important;
            line-height: 1.20 !important;
        }

        div[data-testid="stExpander"] details {
            border-radius: 14px !important;
        }

        div[data-testid="stExpander"] details summary {
            padding-top: 0.55rem !important;
            padding-bottom: 0.55rem !important;
        }

        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                padding-left: 0.86rem !important;
                padding-right: 0.86rem !important;
                padding-top: 0.78rem !important;
                padding-bottom: 1rem !important;
                max-width: 100vw !important;
                min-height: 84svh !important;
            }

            header[data-testid="stHeader"] {
                visibility: visible !important;
                height: 2.72rem !important;
                min-height: 2.72rem !important;
                background: rgba(255,255,255,0.78) !important;
                backdrop-filter: blur(10px);
            }

            section[data-testid="stSidebar"] {
                max-width: 88vw !important;
            }

            .bling-hero {
                width: 100%;
                padding: 14px 12px 15px 12px;
                margin: 0.08rem auto 0.70rem auto;
                border-radius: 17px;
            }

            .bling-hero-row {
                grid-template-columns: 26px minmax(0, 1fr) 30px;
                gap: 5px;
            }

            .bling-hero-title {
                font-size: 1.18rem;
                line-height: 1.22;
                margin-bottom: 6px;
                letter-spacing: normal;
            }

            .bling-hero-subtitle {
                font-size: 0.84rem;
                line-height: 1.38;
            }

            .bling-hero-tech-slot .stButton > button {
                min-height: 28px !important;
                height: 28px !important;
                width: 28px !important;
                font-size: 0.76rem !important;
            }

            .bling-home-button-center {
                width: min(100%, 285px);
                margin-top: 0.95rem;
            }

            .bling-step-title {
                font-size: 1.08rem;
                line-height: 1.28;
                margin: 0.62rem 0 0.18rem 0;
            }

            .bling-muted {
                font-size: 0.86rem;
                line-height: 1.42;
                margin: 0 0 0.62rem 0;
            }

            .bling-compact-note {
                padding: 8px 10px;
                margin: 0.45rem 0 0.58rem 0;
                border-radius: 12px;
                font-size: 0.84rem;
                line-height: 1.38;
            }

            div[data-testid="stVerticalBlock"] {
                gap: 0.46rem !important;
            }

            div[data-testid="stHorizontalBlock"] {
                gap: 0.42rem !important;
            }

            div[data-testid="stMarkdownContainer"] p {
                line-height: 1.36 !important;
                margin-bottom: 0.35rem !important;
            }

            div[data-testid="stFileUploader"] section {
                min-height: 78px !important;
                padding: 9px 10px !important;
                border-radius: 14px !important;
            }

            div[data-testid="stFileUploader"] section p {
                font-size: 0.80rem !important;
                line-height: 1.24 !important;
            }

            div[data-testid="stFileUploader"] small {
                font-size: 0.70rem !important;
                line-height: 1.20 !important;
            }

            div[data-testid="stFileUploader"] button {
                min-height: 36px !important;
                padding: 0.32rem 0.58rem !important;
                font-size: 0.82rem !important;
                line-height: 1.18 !important;
            }

            div[data-testid="stExpander"] details summary p {
                font-size: 0.88rem !important;
                line-height: 1.26 !important;
            }

            div[data-testid="stExpander"] details summary {
                padding: 0.48rem 0.58rem !important;
            }

            .stButton > button,
            .stDownloadButton > button {
                min-height: 46px !important;
                padding: 0.46rem 0.68rem !important;
                font-size: 0.96rem !important;
                line-height: 1.24 !important;
                border-radius: 14px !important;
                white-space: normal !important;
            }

            textarea,
            input,
            div[data-baseweb="input"] input,
            div[data-baseweb="textarea"] textarea {
                font-size: 0.92rem !important;
            }

            div[data-testid="stDataFrame"] {
                max-height: 360px !important;
            }

            iframe,
            div[data-testid="stDataFrame"] > div {
                max-width: 100% !important;
            }
        }

        @media (max-width: 390px) {
            .main .block-container,
            .block-container {
                padding-left: 0.70rem !important;
                padding-right: 0.70rem !important;
                padding-top: 0.68rem !important;
                min-height: 84svh !important;
            }

            header[data-testid="stHeader"] {
                height: 2.6rem !important;
                min-height: 2.6rem !important;
            }

            .bling-hero {
                padding: 13px 10px 14px 10px;
            }

            .bling-hero-title {
                font-size: 1.08rem;
            }

            .bling-hero-subtitle {
                font-size: 0.79rem;
            }

            .bling-step-title {
                font-size: 1rem;
            }

            .bling-muted {
                font-size: 0.80rem;
            }

            .stButton > button,
            .stDownloadButton > button {
                min-height: 44px !important;
                font-size: 0.90rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_compact_hero() -> None:
    from bling_app_zero.core.debug import render_debug_compact_button

    st.markdown('<div class="bling-hero"><div class="bling-hero-row"><div></div><div class="bling-hero-text">', unsafe_allow_html=True)
    st.markdown('<div class="bling-hero-title"><span>🚀 IA Planilhas → Bling</span></div>', unsafe_allow_html=True)
    st.markdown('<p class="bling-hero-subtitle">Transforme dados em CSV pronto para o Bling.</p>', unsafe_allow_html=True)
    st.markdown('</div><div class="bling-hero-tech-slot">', unsafe_allow_html=True)
    render_debug_compact_button()
    st.markdown('</div></div></div>', unsafe_allow_html=True)


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
