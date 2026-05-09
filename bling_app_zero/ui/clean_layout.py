from __future__ import annotations

import html

import streamlit as st


def inject_clean_home_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bling-gap: 0.62rem;
            --bling-radius: 14px;
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
            overflow-x: hidden !important;
            max-width: 100vw !important;
        }

        .block-container {
            padding-top: 1.10rem;
            padding-bottom: 1.2rem;
            max-width: 1060px;
            overflow-x: hidden !important;
        }

        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"],
        div[data-testid="column"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.44rem !important;
        }

        div[data-testid="column"] {
            padding: 0 0.15rem !important;
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
            padding: 12px 14px;
            margin: 0 0 var(--bling-gap) 0;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,249,251,0.92));
            overflow: hidden;
        }
        .bling-hero-title {
            font-size: clamp(1.24rem, 4.6vw, 1.9rem);
            line-height: 1.14;
            font-weight: 800;
            margin: 0 0 5px 0;
            overflow-wrap: anywhere;
        }
        .bling-hero-subtitle {
            font-size: clamp(0.84rem, 3.2vw, 0.96rem);
            line-height: 1.32;
            color: rgba(49, 51, 63, 0.72);
            margin: 0;
            overflow-wrap: anywhere;
        }

        .bling-step-title {
            font-size: 1.08rem;
            line-height: 1.18;
            font-weight: 800;
            margin: 8px 0 4px 0;
            overflow-wrap: anywhere;
            clear: both;
        }
        .bling-muted {
            color: rgba(49, 51, 63, 0.66);
            font-size: 0.86rem;
            line-height: 1.28;
            margin: 0 0 0.45rem 0;
            overflow-wrap: anywhere;
            clear: both;
        }
        .bling-compact-note {
            border-radius: 11px;
            padding: 7px 9px;
            background: rgba(240, 242, 246, 0.72);
            color: rgba(49, 51, 63, 0.76);
            font-size: 0.82rem;
            line-height: 1.26;
            margin: 5px 0 8px 0;
            overflow-wrap: anywhere;
        }
        .bling-upload-title {
            font-size: 1rem;
            font-weight: 800;
            margin: 7px 0 2px 0;
            line-height: 1.18;
        }
        .bling-upload-caption {
            color: rgba(49, 51, 63, 0.62);
            font-size: 0.82rem;
            line-height: 1.24;
            margin: 0 0 5px 0;
        }

        /* Card REAL do mapeamento: container externo do Streamlit, sem card duplicado no select. */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
            border-radius: 13px !important;
            border: 1px solid rgba(49, 51, 63, 0.13) !important;
            background: rgba(248, 250, 252, 0.92) !important;
            padding: 7px 8px 6px 8px !important;
            margin: 3px 0 6px 0 !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.035) !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
            gap: 0.16rem !important;
        }

        /* Select limpo dentro do card: sem borda externa, sem margem gigante, sem deslizar. */
        div[data-testid="stSelectbox"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
            padding: 0 !important;
            margin: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
        }
        div[data-testid="stSelectbox"] label {
            margin: 0 0 3px 0 !important;
            padding: 0 !important;
        }
        div[data-testid="stSelectbox"] label p {
            font-weight: 760 !important;
            letter-spacing: -0.01em !important;
            line-height: 1.08 !important;
            margin: 0 !important;
        }
        div[data-baseweb="select"] {
            max-width: 100% !important;
            width: 100% !important;
            margin: 0 !important;
        }
        div[data-baseweb="select"] > div {
            max-width: 100% !important;
            min-height: 39px !important;
            overflow: hidden !important;
            background: #eef2f7 !important;
            border: 1px solid rgba(49, 51, 63, 0.11) !important;
            border-radius: 12px !important;
            box-shadow: none !important;
        }
        div[data-baseweb="select"] [data-testid="stMarkdownContainer"],
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div {
            max-width: 100% !important;
            overflow-x: hidden !important;
            text-overflow: ellipsis !important;
        }

        /* Preview da primeira linha dentro do mesmo card: colado no select. */
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stMarkdownContainer"] > div[style*="font-size:11px"] {
            font-size: 10px !important;
            line-height: 1.02 !important;
            margin-top: -5px !important;
            margin-bottom: -2px !important;
            padding: 1px 4px !important;
            border-radius: 6px !important;
            max-width: 100% !important;
            overflow-wrap: anywhere !important;
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
            border-radius: 13px !important;
            min-height: 42px;
            padding: 0.42rem 0.62rem;
            font-size: 0.92rem;
            line-height: 1.18;
            white-space: normal;
        }

        div[data-testid="stFileUploader"] section {
            padding: 9px 10px !important;
            min-height: 76px !important;
            border-radius: 13px !important;
        }
        div[data-testid="stFileUploader"] section p {
            font-size: 0.82rem !important;
            line-height: 1.18 !important;
            margin-bottom: 0.10rem !important;
        }
        div[data-testid="stFileUploader"] small {
            font-size: 0.70rem !important;
            line-height: 1.14 !important;
        }
        div[data-testid="stExpander"] details {
            border-radius: 13px !important;
        }
        div[data-testid="stExpander"] details summary {
            padding-top: 0.46rem !important;
            padding-bottom: 0.46rem !important;
        }

        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                padding-left: 0.48rem !important;
                padding-right: 0.48rem !important;
                padding-top: 1.70rem !important;
                padding-bottom: 0.85rem !important;
                max-width: 100vw !important;
                min-height: 84svh !important;
                overflow-x: hidden !important;
            }
            header[data-testid="stHeader"] {
                visibility: visible !important;
                height: 2.65rem !important;
                min-height: 2.65rem !important;
                background: rgba(255,255,255,0.78) !important;
                backdrop-filter: blur(10px);
            }
            section[data-testid="stSidebar"] {
                max-width: 88vw !important;
            }
            div[data-testid="stVerticalBlock"] {
                gap: 0.40rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                gap: 0.34rem !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 6px 7px 5px 7px !important;
                margin: 2px 0 5px 0 !important;
                border-radius: 12px !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
                gap: 0.10rem !important;
            }
            div[data-baseweb="select"] > div {
                min-height: 38px !important;
                border-radius: 11px !important;
            }
            div[data-testid="stSelectbox"] label {
                margin-bottom: 2px !important;
            }
            .bling-hero {
                padding: 10px 11px;
                margin: 0 0 0.56rem 0;
                border-radius: 14px;
            }
            .bling-hero-title {
                font-size: 1.08rem;
                line-height: 1.15;
                margin-bottom: 4px;
            }
            .bling-hero-subtitle {
                font-size: 0.80rem;
                line-height: 1.28;
            }
            .bling-step-title {
                font-size: 1.02rem;
                line-height: 1.18;
                margin: 0.50rem 0 0.14rem 0;
                display: block;
            }
            .bling-muted {
                font-size: 0.80rem;
                line-height: 1.25;
                margin: 0 0 0.42rem 0;
                display: block;
            }
            .bling-compact-note {
                padding: 7px 8px;
                margin: 0.36rem 0 0.46rem 0;
                border-radius: 11px;
                font-size: 0.78rem;
                line-height: 1.24;
            }
            .bling-upload-title {
                font-size: 0.96rem;
                line-height: 1.18;
                margin: 0.45rem 0 0.14rem 0;
            }
            .bling-upload-caption {
                font-size: 0.78rem;
                line-height: 1.23;
                margin: 0 0 0.36rem 0;
            }
            div[data-testid="stMarkdownContainer"] p {
                line-height: 1.24 !important;
                margin-bottom: 0.28rem !important;
            }
            div[role="radiogroup"] label {
                border: 1px solid rgba(49, 51, 63, 0.14);
                border-radius: 13px;
                padding: 8px 9px !important;
                background: rgba(250, 250, 250, 0.84);
                margin-bottom: 5px !important;
                width: 100%;
                min-height: 44px;
                align-items: center;
                overflow: hidden;
            }
            div[role="radiogroup"] label p,
            div[role="radiogroup"] label span,
            div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
                font-size: 0.88rem !important;
                line-height: 1.18 !important;
                white-space: normal !important;
                overflow-wrap: anywhere !important;
                margin: 0 !important;
            }
            div[data-testid="stFileUploader"] section {
                min-height: 72px !important;
                padding: 8px 9px !important;
                border-radius: 13px !important;
            }
            div[data-testid="stFileUploader"] section p {
                font-size: 0.76rem !important;
                line-height: 1.16 !important;
            }
            div[data-testid="stFileUploader"] small {
                font-size: 0.68rem !important;
                line-height: 1.12 !important;
            }
            div[data-testid="stFileUploader"] button {
                min-height: 34px !important;
                padding: 0.30rem 0.52rem !important;
                font-size: 0.78rem !important;
                line-height: 1.10 !important;
            }
            div[data-testid="stExpander"] details summary p {
                font-size: 0.84rem !important;
                line-height: 1.18 !important;
            }
            div[data-testid="stExpander"] details summary {
                padding: 0.42rem 0.52rem !important;
            }
            .stButton > button,
            .stDownloadButton > button {
                min-height: 42px !important;
                padding: 0.40rem 0.60rem !important;
                font-size: 0.90rem !important;
                line-height: 1.16 !important;
                border-radius: 13px !important;
                white-space: normal !important;
            }
            textarea,
            input,
            div[data-baseweb="input"] input,
            div[data-baseweb="textarea"] textarea {
                font-size: 0.88rem !important;
            }
            div[data-testid="stDataFrame"] {
                max-height: 340px !important;
            }
            iframe,
            div[data-testid="stDataFrame"] > div {
                max-width: 100% !important;
            }
        }

        @media (max-width: 390px) {
            .main .block-container,
            .block-container {
                padding-left: 0.42rem !important;
                padding-right: 0.42rem !important;
                padding-top: 1.58rem !important;
            }
            header[data-testid="stHeader"] {
                height: 2.55rem !important;
                min-height: 2.55rem !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 5px 6px 5px 6px !important;
                margin: 2px 0 5px 0 !important;
            }
            div[data-baseweb="select"] > div {
                min-height: 37px !important;
            }
            .bling-hero {
                padding: 9px 10px;
                margin-bottom: 0.48rem;
            }
            .bling-hero-title {
                font-size: 1.02rem;
            }
            .bling-hero-subtitle {
                font-size: 0.76rem;
            }
            .bling-step-title {
                font-size: 0.98rem;
            }
            .bling-muted {
                font-size: 0.76rem;
            }
            .stButton > button,
            .stDownloadButton > button {
                min-height: 40px !important;
                font-size: 0.86rem !important;
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
