from __future__ import annotations

import html

import streamlit as st


def inject_clean_home_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bling-gap: 0.72rem;
            --bling-radius: 16px;
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
            overflow-x: hidden !important;
            max-width: 100vw !important;
        }

        .block-container {
            padding-top: 1.15rem;
            padding-bottom: 1.5rem;
            max-width: 1060px;
            overflow-x: hidden !important;
        }

        div[data-testid="stMarkdownContainer"] h1,
        div[data-testid="stMarkdownContainer"] h2,
        div[data-testid="stMarkdownContainer"] h3,
        div[data-testid="stMarkdownContainer"] h4 {
            letter-spacing: -0.02em;
        }

        .bling-hero {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: var(--bling-radius);
            padding: 14px 16px 13px 16px;
            margin: 0 0 var(--bling-gap) 0;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,249,251,0.92));
            overflow: hidden;
        }
        .bling-hero-title {
            font-size: clamp(1.32rem, 5vw, 2rem);
            line-height: 1.16;
            font-weight: 800;
            margin: 0 0 6px 0;
            overflow-wrap: anywhere;
        }
        .bling-hero-subtitle {
            font-size: clamp(0.90rem, 3.4vw, 1rem);
            line-height: 1.36;
            color: rgba(49, 51, 63, 0.72);
            margin: 0;
            overflow-wrap: anywhere;
        }

        .bling-step-title {
            font-size: 1.14rem;
            line-height: 1.22;
            font-weight: 800;
            margin: 10px 0 5px 0;
            overflow-wrap: anywhere;
            clear: both;
        }
        .bling-muted {
            color: rgba(49, 51, 63, 0.66);
            font-size: 0.92rem;
            line-height: 1.34;
            margin: 0 0 0.62rem 0;
            overflow-wrap: anywhere;
            clear: both;
        }
        .bling-compact-note {
            border-radius: 12px;
            padding: 9px 11px;
            background: rgba(240, 242, 246, 0.72);
            color: rgba(49, 51, 63, 0.76);
            font-size: 0.88rem;
            line-height: 1.32;
            margin: 7px 0 10px 0;
            overflow-wrap: anywhere;
        }
        .bling-upload-title {
            font-size: 1.10rem;
            font-weight: 800;
            margin: 9px 0 3px 0;
            line-height: 1.22;
        }
        .bling-upload-caption {
            color: rgba(49, 51, 63, 0.62);
            font-size: 0.88rem;
            line-height: 1.30;
            margin: 0 0 7px 0;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.58rem !important;
            max-width: 100% !important;
        }
        div[data-testid="column"] {
            padding: 0 0.2rem !important;
        }

        /* Cartão visual para cada campo de mapeamento */
        div[data-testid="stSelectbox"] {
            border: 1px solid rgba(49, 51, 63, 0.10) !important;
            border-radius: 16px !important;
            background: rgba(248, 250, 252, 0.90) !important;
            padding: 10px 10px 12px 10px !important;
            margin: 4px 0 8px 0 !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
            max-width: 100% !important;
            overflow-x: hidden !important;
        }
        div[data-testid="stSelectbox"] label {
            margin-bottom: 7px !important;
        }
        div[data-testid="stSelectbox"] label p {
            font-weight: 750 !important;
            letter-spacing: -0.01em !important;
        }

        /* Preview da primeira linha: continuação do cartão acima */
        div[data-testid="stSelectbox"] + div[data-testid="stElementContainer"] {
            border-left: 1px solid rgba(49, 51, 63, 0.10) !important;
            border-right: 1px solid rgba(49, 51, 63, 0.10) !important;
            border-bottom: 1px solid rgba(49, 51, 63, 0.10) !important;
            border-radius: 0 0 16px 16px !important;
            background: rgba(248, 250, 252, 0.90) !important;
            padding: 0 10px 9px 10px !important;
            margin: -18px 0 11px 0 !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
            max-width: 100% !important;
            overflow-x: hidden !important;
        }
        div[data-testid="stSelectbox"] + div[data-testid="stElementContainer"] div[data-testid="stMarkdownContainer"] > div {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
            padding: 6px 8px !important;
            border-radius: 10px !important;
            background: rgba(232, 247, 238, 0.58) !important;
            overflow-wrap: anywhere !important;
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
        div[data-baseweb="menu"] {
            max-width: calc(100vw - 24px) !important;
            overflow-x: hidden !important;
        }
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
            line-height: 1.22;
            white-space: normal;
        }
        div[data-testid="stFileUploader"] section {
            padding: 11px 12px !important;
            min-height: 82px !important;
            border-radius: 14px !important;
        }
        div[data-testid="stFileUploader"] section p {
            font-size: 0.86rem !important;
            line-height: 1.22 !important;
            margin-bottom: 0.15rem !important;
        }
        div[data-testid="stFileUploader"] small {
            font-size: 0.74rem !important;
            line-height: 1.18 !important;
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
                padding-left: 0.62rem !important;
                padding-right: 0.62rem !important;
                padding-top: 1.80rem !important;
                padding-bottom: 1rem !important;
                max-width: 100vw !important;
                min-height: 84svh !important;
                overflow-x: hidden !important;
            }
            header[data-testid="stHeader"] {
                visibility: visible !important;
                height: 2.75rem !important;
                min-height: 2.75rem !important;
                background: rgba(255,255,255,0.78) !important;
                backdrop-filter: blur(10px);
            }
            section[data-testid="stSidebar"] {
                max-width: 88vw !important;
            }
            div[data-testid="stVerticalBlock"],
            div[data-testid="stHorizontalBlock"],
            div[data-testid="stElementContainer"] {
                max-width: 100% !important;
                overflow-x: hidden !important;
            }
            div[data-testid="stSelectbox"] {
                padding: 9px 9px 11px 9px !important;
                margin: 5px 0 9px 0 !important;
                border-radius: 15px !important;
                background: rgba(248, 250, 252, 0.96) !important;
            }
            div[data-testid="stSelectbox"] + div[data-testid="stElementContainer"] {
                padding: 0 9px 9px 9px !important;
                margin: -19px 0 11px 0 !important;
                border-radius: 0 0 15px 15px !important;
                background: rgba(248, 250, 252, 0.96) !important;
            }
            div[data-baseweb="select"] > div {
                min-height: 46px !important;
                background: #eef2f7 !important;
                border: 1px solid rgba(49, 51, 63, 0.12) !important;
            }
            .bling-hero {
                padding: 11px 12px 10px 12px;
                margin: 0 0 0.70rem 0;
                border-radius: 15px;
            }
            .bling-hero-title {
                font-size: 1.17rem;
                line-height: 1.18;
                margin-bottom: 5px;
            }
            .bling-hero-subtitle {
                font-size: 0.86rem;
                line-height: 1.34;
            }
            .bling-step-title {
                font-size: 1.08rem;
                line-height: 1.22;
                margin: 0.62rem 0 0.18rem 0;
                display: block;
            }
            .bling-muted {
                font-size: 0.86rem;
                line-height: 1.32;
                margin: 0 0 0.62rem 0;
                display: block;
            }
            .bling-compact-note {
                padding: 8px 10px;
                margin: 0.45rem 0 0.58rem 0;
                border-radius: 12px;
                font-size: 0.84rem;
                line-height: 1.30;
            }
            .bling-upload-title {
                font-size: 1rem;
                line-height: 1.22;
                margin: 0.55rem 0 0.18rem 0;
            }
            .bling-upload-caption {
                font-size: 0.82rem;
                line-height: 1.28;
                margin: 0 0 0.45rem 0;
            }
            div[data-testid="stVerticalBlock"] {
                gap: 0.54rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                gap: 0.42rem !important;
            }
            div[data-testid="stMarkdownContainer"] p {
                line-height: 1.30 !important;
                margin-bottom: 0.35rem !important;
            }
            div[role="radiogroup"] label {
                border: 1px solid rgba(49, 51, 63, 0.14);
                border-radius: 14px;
                padding: 9px 10px !important;
                background: rgba(250, 250, 250, 0.84);
                margin-bottom: 6px !important;
                width: 100%;
                min-height: 48px;
                align-items: center;
                overflow: hidden;
            }
            div[role="radiogroup"] label p,
            div[role="radiogroup"] label span,
            div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
                font-size: 0.94rem !important;
                line-height: 1.22 !important;
                white-space: normal !important;
                overflow-wrap: anywhere !important;
                margin: 0 !important;
            }
            div[data-testid="stFileUploader"] section {
                min-height: 78px !important;
                padding: 9px 10px !important;
                border-radius: 14px !important;
            }
            div[data-testid="stFileUploader"] section p {
                font-size: 0.80rem !important;
                line-height: 1.20 !important;
            }
            div[data-testid="stFileUploader"] small {
                font-size: 0.70rem !important;
                line-height: 1.16 !important;
            }
            div[data-testid="stFileUploader"] button {
                min-height: 36px !important;
                padding: 0.32rem 0.58rem !important;
                font-size: 0.82rem !important;
                line-height: 1.12 !important;
            }
            div[data-testid="stExpander"] details summary p {
                font-size: 0.88rem !important;
                line-height: 1.22 !important;
            }
            div[data-testid="stExpander"] details summary {
                padding: 0.48rem 0.58rem !important;
            }
            .stButton > button,
            .stDownloadButton > button {
                min-height: 46px !important;
                padding: 0.46rem 0.68rem !important;
                font-size: 0.96rem !important;
                line-height: 1.20 !important;
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
                padding-left: 0.50rem !important;
                padding-right: 0.50rem !important;
                padding-top: 1.65rem !important;
                min-height: 84svh !important;
            }
            header[data-testid="stHeader"] {
                height: 2.6rem !important;
                min-height: 2.6rem !important;
            }
            .bling-hero {
                padding: 10px 11px 9px 11px;
                margin-bottom: 0.55rem;
            }
            .bling-hero-title {
                font-size: 1.08rem;
            }
            .bling-hero-subtitle {
                font-size: 0.80rem;
            }
            .bling-step-title {
                font-size: 1rem;
            }
            .bling-muted {
                font-size: 0.80rem;
            }
            div[data-testid="stSelectbox"] {
                padding: 8px 8px 10px 8px !important;
                border-radius: 14px !important;
            }
            div[data-testid="stSelectbox"] + div[data-testid="stElementContainer"] {
                padding: 0 8px 8px 8px !important;
                margin-top: -18px !important;
                border-radius: 0 0 14px 14px !important;
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
    st.markdown(
        """
        <div class="bling-hero">
            <div class="bling-hero-title">🚀 IA Planilhas → Bling</div>
            <p class="bling-hero-subtitle">Busque produtos ou envie arquivos e gere planilhas no padrão Bling, prontas para importar.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_title(title: str, caption: str | None = None) -> None:
    safe_title = html.escape(str(title or ''))
    st.markdown(f'<div class="bling-step-title">{safe_title}</div>', unsafe_allow_html=True)
    if caption:
        safe_caption = html.escape(str(caption or ''))
        st.markdown(f'<div class="bling-muted">{safe_caption}</div>', unsafe_allow_html=True)


def render_compact_note(text: str) -> None:
    safe_text = html.escape(str(text or ''))
    st.markdown(f'<div class="bling-compact-note">{safe_text}</div>', unsafe_allow_html=True)
