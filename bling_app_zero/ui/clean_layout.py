from __future__ import annotations

import html

import streamlit as st


def inject_clean_home_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1.4rem;
            max-width: 1080px;
        }
        div[data-testid="stMarkdownContainer"] h1,
        div[data-testid="stMarkdownContainer"] h2,
        div[data-testid="stMarkdownContainer"] h3,
        div[data-testid="stMarkdownContainer"] h4 {
            letter-spacing: -0.02em;
        }
        .bling-hero {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 16px;
            padding: 14px 16px 12px 16px;
            margin: 0 0 12px 0;
            background: rgba(250, 250, 250, 0.72);
            overflow: hidden;
        }
        .bling-hero-title {
            font-size: clamp(1.35rem, 5vw, 2rem);
            line-height: 1.08;
            font-weight: 800;
            margin: 0 0 6px 0;
            overflow-wrap: anywhere;
        }
        .bling-hero-subtitle {
            font-size: clamp(0.88rem, 3.4vw, 1rem);
            line-height: 1.28;
            color: rgba(49, 51, 63, 0.72);
            margin: 0;
            overflow-wrap: anywhere;
        }
        .bling-step-title {
            font-size: 1.08rem;
            line-height: 1.16;
            font-weight: 800;
            margin: 8px 0 3px 0;
            overflow-wrap: anywhere;
        }
        .bling-muted {
            color: rgba(49, 51, 63, 0.65);
            font-size: 0.9rem;
            line-height: 1.23;
            margin-bottom: 0.48rem;
            overflow-wrap: anywhere;
        }
        .bling-compact-note {
            border-radius: 11px;
            padding: 8px 10px;
            background: rgba(240, 242, 246, 0.72);
            color: rgba(49, 51, 63, 0.76);
            font-size: 0.86rem;
            line-height: 1.22;
            margin: 6px 0 9px 0;
            overflow-wrap: anywhere;
        }
        .bling-upload-title {
            font-size: 1.08rem;
            font-weight: 800;
            margin: 7px 0 2px 0;
            line-height: 1.16;
        }
        .bling-upload-caption {
            color: rgba(49, 51, 63, 0.62);
            font-size: 0.86rem;
            line-height: 1.22;
            margin: 0 0 6px 0;
        }
        div[data-testid="stFileUploader"] section {
            padding: 10px 10px !important;
            min-height: 76px !important;
        }
        div[data-testid="stFileUploader"] section > div {
            gap: 0.25rem !important;
        }
        div[data-testid="stFileUploader"] section p {
            font-size: 0.84rem !important;
            line-height: 1.12 !important;
            margin-bottom: 0.10rem !important;
        }
        div[data-testid="stFileUploader"] small {
            font-size: 0.72rem !important;
        }
        div[data-testid="stVerticalBlock"] {
            gap: 0.42rem !important;
        }
        div[data-testid="column"] {
            padding: 0 0.18rem !important;
        }
        .stButton > button,
        .stDownloadButton > button {
            border-radius: 12px !important;
            min-height: 42px;
            padding: 0.42rem 0.62rem;
            font-size: 0.92rem;
            line-height: 1.18;
            white-space: normal;
        }
        div[data-testid="stExpander"] details {
            border-radius: 12px !important;
        }
        div[data-testid="stExpander"] details summary {
            padding-top: 0.45rem !important;
            padding-bottom: 0.45rem !important;
        }
        div[data-testid="stDataFrame"] {
            font-size: 0.8rem !important;
        }

        @media (max-width: 760px) {
            html, body, [data-testid="stAppViewContainer"] {
                overflow-x: hidden !important;
            }
            .main .block-container,
            .block-container {
                padding-left: 0.42rem !important;
                padding-right: 0.42rem !important;
                padding-top: 0.22rem !important;
                padding-bottom: 0.65rem !important;
                max-width: calc(100vw - 0.20rem) !important;
                width: calc(100vw - 0.20rem) !important;
            }
            header[data-testid="stHeader"] {
                height: 0 !important;
                min-height: 0 !important;
                visibility: hidden;
            }
            section[data-testid="stSidebar"] {
                max-width: 86vw !important;
            }
            .bling-hero {
                padding: 8px 10px 7px 10px;
                margin: 0 0 7px 0;
                border-radius: 13px;
            }
            .bling-hero-title {
                font-size: 1.06rem;
                line-height: 1.04;
                white-space: normal;
                margin-bottom: 4px;
            }
            .bling-hero-subtitle {
                font-size: 0.78rem;
                line-height: 1.18;
            }
            .bling-step-title {
                font-size: 0.98rem;
                line-height: 1.08;
                margin: 5px 0 1px 0;
            }
            .bling-muted {
                font-size: 0.78rem;
                line-height: 1.16;
                margin-bottom: 0.28rem;
            }
            .bling-compact-note {
                padding: 6px 8px;
                margin: 4px 0 6px 0;
                border-radius: 10px;
                font-size: 0.76rem;
                line-height: 1.16;
            }
            .bling-upload-title {
                font-size: 0.92rem;
                line-height: 1.10;
                margin: 4px 0 1px 0;
            }
            .bling-upload-caption {
                font-size: 0.74rem;
                line-height: 1.14;
                margin: 0 0 3px 0;
            }
            div[data-testid="stVerticalBlock"] {
                gap: 0.28rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                gap: 0.28rem !important;
            }
            div[data-testid="column"] {
                padding: 0 0.08rem !important;
            }
            div[data-testid="stMarkdownContainer"] p {
                margin-bottom: 0.18rem !important;
                line-height: 1.16 !important;
            }
            div[role="radiogroup"] {
                gap: 0.18rem !important;
            }
            div[role="radiogroup"] label {
                border: 1px solid rgba(49, 51, 63, 0.14);
                border-radius: 11px;
                padding: 5px 7px !important;
                background: rgba(250, 250, 250, 0.78);
                margin-bottom: 3px !important;
                width: 100%;
                min-height: 38px;
                align-items: center;
                overflow: hidden;
            }
            div[role="radiogroup"] label > div:first-child {
                margin-right: 0.35rem !important;
                flex: 0 0 auto;
                transform: scale(0.88);
            }
            div[role="radiogroup"] label p,
            div[role="radiogroup"] label span,
            div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
                font-size: 0.82rem !important;
                line-height: 1.10 !important;
                white-space: normal !important;
                overflow-wrap: anywhere !important;
                word-break: normal !important;
                margin: 0 !important;
            }
            div[data-testid="stFileUploader"] section {
                min-height: 58px !important;
                padding: 6px 7px !important;
                border-radius: 11px !important;
            }
            div[data-testid="stFileUploader"] section p {
                font-size: 0.70rem !important;
                line-height: 1.04 !important;
            }
            div[data-testid="stFileUploader"] small {
                font-size: 0.62rem !important;
                line-height: 1.04 !important;
            }
            div[data-testid="stFileUploader"] button {
                min-height: 30px !important;
                padding: 0.18rem 0.45rem !important;
                font-size: 0.74rem !important;
                line-height: 1.05 !important;
            }
            div[data-testid="stExpander"] details summary p {
                font-size: 0.80rem !important;
                line-height: 1.10 !important;
            }
            div[data-testid="stExpander"] details summary {
                padding: 0.35rem 0.45rem !important;
            }
            div[data-testid="stExpander"] div[role="button"] p {
                font-size: 0.80rem !important;
            }
            .stButton > button,
            .stDownloadButton > button {
                min-height: 38px !important;
                padding: 0.32rem 0.48rem !important;
                font-size: 0.82rem !important;
                line-height: 1.10 !important;
                border-radius: 11px !important;
                white-space: normal !important;
            }
            textarea,
            input,
            div[data-baseweb="input"] input,
            div[data-baseweb="textarea"] textarea {
                font-size: 0.82rem !important;
            }
            div[data-baseweb="input"],
            div[data-baseweb="textarea"] {
                border-radius: 10px !important;
            }
            div[data-testid="stDataFrame"] {
                max-height: 300px !important;
            }
            iframe,
            div[data-testid="stDataFrame"] > div {
                max-width: 100% !important;
            }
        }

        @media (max-width: 390px) {
            .main .block-container,
            .block-container {
                padding-left: 0.32rem !important;
                padding-right: 0.32rem !important;
                max-width: calc(100vw - 0.10rem) !important;
                width: calc(100vw - 0.10rem) !important;
            }
            .bling-hero {
                padding: 7px 8px 6px 8px;
                margin-bottom: 6px;
            }
            .bling-hero-title {
                font-size: 0.98rem;
            }
            .bling-hero-subtitle,
            .bling-muted,
            .bling-compact-note {
                font-size: 0.72rem;
            }
            .bling-step-title {
                font-size: 0.92rem;
            }
            div[role="radiogroup"] label {
                min-height: 35px;
                padding: 4px 6px !important;
            }
            div[role="radiogroup"] label p,
            div[role="radiogroup"] label span,
            div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
                font-size: 0.76rem !important;
            }
            .stButton > button,
            .stDownloadButton > button {
                min-height: 35px !important;
                font-size: 0.77rem !important;
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
