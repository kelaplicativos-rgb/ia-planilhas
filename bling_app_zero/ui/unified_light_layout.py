from __future__ import annotations

import streamlit as st


def inject_unified_light_layout() -> None:
    """Tema global único, leve e centralizado.

    Este módulo fica separado para não bagunçar os motores, fluxos e regras do app.
    Ele só aplica a identidade visual aprovada: tela limpa, card central,
    cantos arredondados, espaçamento suave e comportamento responsivo.
    """
    st.markdown(
        """
        <style>
        :root {
            --bling-bg: #f8fafc;
            --bling-panel: rgba(255, 255, 255, 0.92);
            --bling-panel-strong: rgba(255, 255, 255, 0.98);
            --bling-border: rgba(15, 23, 42, 0.12);
            --bling-border-soft: rgba(15, 23, 42, 0.075);
            --bling-text: #172033;
            --bling-muted: rgba(51, 65, 85, 0.72);
            --bling-shadow: 0 18px 60px rgba(15, 23, 42, 0.055);
            --bling-radius-lg: 22px;
            --bling-radius-md: 16px;
            --bling-radius-sm: 12px;
            --bling-flow-gap: 0.82rem;
            --bling-section-gap: 1.08rem;
        }

        html,
        body,
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 50% 0%, rgba(226, 232, 240, 0.72), transparent 36rem),
                linear-gradient(180deg, #ffffff 0%, var(--bling-bg) 100%) !important;
            color: var(--bling-text) !important;
            overflow-x: hidden !important;
        }

        header[data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.76) !important;
            backdrop-filter: blur(12px) !important;
            border-bottom: 1px solid rgba(226, 232, 240, 0.58) !important;
        }

        .main .block-container,
        .block-container {
            width: min(100%, 1006px) !important;
            max-width: 1006px !important;
            margin: 0 auto !important;
            padding: 4.7rem 0.82rem 2rem 0.82rem !important;
            box-sizing: border-box !important;
        }

        .main .block-container > div:first-child {
            border: 1px solid var(--bling-border) !important;
            border-radius: 24px !important;
            background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(248,250,252,0.84)) !important;
            box-shadow: var(--bling-shadow) !important;
            padding: 2.65rem 0.85rem 1.3rem 0.85rem !important;
            min-height: calc(100vh - 8.2rem) !important;
            overflow: hidden !important;
        }

        .bling-hero {
            width: min(100%, 860px) !important;
            margin: 0 auto 0.95rem auto !important;
            padding: 15px 18px 14px 18px !important;
            border: 1px solid var(--bling-border-soft) !important;
            border-radius: 14px !important;
            background: linear-gradient(180deg, var(--bling-panel-strong), rgba(248,250,252,0.94)) !important;
            box-shadow: 0 10px 34px rgba(15, 23, 42, 0.035) !important;
            text-align: center !important;
        }

        .bling-hero-title {
            color: var(--bling-text) !important;
            font-size: clamp(1.45rem, 3.1vw, 2.05rem) !important;
            font-weight: 950 !important;
            letter-spacing: -0.035em !important;
            line-height: 1.12 !important;
            margin: 0 0 7px 0 !important;
        }

        .bling-hero-subtitle {
            color: var(--bling-muted) !important;
            font-size: 0.98rem !important;
            line-height: 1.35 !important;
            margin: 0 auto !important;
            max-width: 760px !important;
        }

        .bling-home-center,
        div[data-testid="stHorizontalBlock"] {
            width: 100% !important;
            box-sizing: border-box !important;
        }

        .bling-home-card,
        div[data-testid="stExpander"] details,
        div[data-testid="stFileUploader"] section {
            border: 1px solid var(--bling-border-soft) !important;
            border-radius: var(--bling-radius-md) !important;
            background: var(--bling-panel) !important;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.026) !important;
        }

        .bling-home-card {
            width: min(100%, 760px) !important;
            padding: 18px !important;
            margin: 0 auto 0.95rem auto !important;
        }

        div[data-testid="column"] {
            min-width: 0 !important;
            padding: 0 0.28rem !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: var(--bling-flow-gap) !important;
        }

        div[data-testid="stElementContainer"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }

        .bling-step-title,
        h1, h2, h3, h4, h5 {
            color: var(--bling-text) !important;
            font-weight: 900 !important;
            letter-spacing: -0.028em !important;
            line-height: 1.18 !important;
        }

        .bling-step-title,
        div[data-testid="stMarkdownContainer"] h1,
        div[data-testid="stMarkdownContainer"] h2,
        div[data-testid="stMarkdownContainer"] h3,
        div[data-testid="stMarkdownContainer"] h4,
        div[data-testid="stMarkdownContainer"] h5 {
            display: block !important;
            clear: both !important;
            padding-top: 0.28rem !important;
            margin-top: var(--bling-section-gap) !important;
            margin-bottom: 0.45rem !important;
        }

        .bling-hero + div .bling-step-title,
        .bling-hero + div h1,
        .bling-hero + div h2,
        .bling-hero + div h3 {
            margin-top: 0.75rem !important;
        }

        .bling-muted,
        .bling-upload-caption,
        div[data-testid="stCaptionContainer"],
        div[data-testid="stMarkdownContainer"] p {
            color: var(--bling-muted) !important;
            line-height: 1.38 !important;
        }

        .bling-upload-title {
            display: block !important;
            clear: both !important;
            margin: 1.02rem 0 0.22rem 0 !important;
            padding-top: 0.2rem !important;
            color: var(--bling-text) !important;
            font-size: 1.04rem !important;
            font-weight: 900 !important;
            line-height: 1.22 !important;
        }

        .bling-upload-caption {
            display: block !important;
            margin: 0 0 0.58rem 0 !important;
            font-size: 0.88rem !important;
        }

        .stAlert {
            border-radius: var(--bling-radius-sm) !important;
            border: 1px solid rgba(15, 23, 42, 0.065) !important;
            margin: 0.45rem 0 0.72rem 0 !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFileUploader"] button {
            border-radius: 13px !important;
            min-height: 43px !important;
            border: 1px solid rgba(15, 23, 42, 0.13) !important;
            background: rgba(255, 255, 255, 0.95) !important;
            color: var(--bling-text) !important;
            box-shadow: 0 5px 16px rgba(15, 23, 42, 0.035) !important;
            font-weight: 760 !important;
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        div[data-testid="stFileUploader"] button:hover {
            transform: translateY(-1px) !important;
            border-color: rgba(15, 23, 42, 0.22) !important;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.055) !important;
        }

        div[data-testid="stFileUploader"] {
            margin: 0.38rem 0 0.78rem 0 !important;
        }

        div[data-testid="stFileUploader"] section {
            padding: 16px !important;
            min-height: 96px !important;
        }

        div[data-testid="stFileUploader"] section > div {
            gap: 0.45rem !important;
        }

        input,
        textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            border-radius: 13px !important;
            background: rgba(255, 255, 255, 0.94) !important;
            border-color: rgba(15, 23, 42, 0.12) !important;
        }

        div[data-testid="stTextArea"],
        div[data-testid="stTextInput"],
        div[data-testid="stSelectbox"],
        div[data-testid="stNumberInput"],
        div[data-testid="stRadio"] {
            margin: 0.18rem 0 0.55rem 0 !important;
        }

        div[data-testid="stDataFrame"] {
            border-radius: var(--bling-radius-md) !important;
            overflow: hidden !important;
            border: 1px solid var(--bling-border-soft) !important;
            background: #ffffff !important;
            margin: 0.48rem 0 0.62rem 0 !important;
        }

        div[data-testid="stExpander"] {
            margin: 0.62rem 0 0.78rem 0 !important;
        }

        div[data-testid="stExpander"] details summary {
            padding: 0.72rem 0.86rem !important;
        }

        div[data-testid="stExpander"] details > div {
            padding-top: 0.55rem !important;
        }

        section[data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.96) !important;
            border-right: 1px solid rgba(226, 232, 240, 0.9) !important;
        }

        #MainMenu,
        footer {
            visibility: hidden !important;
        }

        @media (max-width: 760px) {
            :root {
                --bling-flow-gap: 0.68rem;
                --bling-section-gap: 0.92rem;
            }

            .main .block-container,
            .block-container {
                width: 100% !important;
                max-width: 100vw !important;
                padding: 3.5rem 0.62rem 1rem 0.62rem !important;
            }

            .main .block-container > div:first-child {
                border-radius: 18px !important;
                padding: 0.85rem 0.58rem 0.95rem 0.58rem !important;
                min-height: calc(100vh - 5rem) !important;
            }

            .bling-hero {
                border-radius: 14px !important;
                padding: 12px 11px !important;
                margin-bottom: 0.7rem !important;
            }

            .bling-hero-title {
                font-size: 1.24rem !important;
            }

            .bling-hero-subtitle {
                font-size: 0.84rem !important;
            }

            .bling-home-card {
                padding: 13px 11px !important;
                border-radius: 15px !important;
            }

            div[data-testid="column"] {
                padding: 0 0.12rem !important;
            }

            .bling-step-title,
            div[data-testid="stMarkdownContainer"] h1,
            div[data-testid="stMarkdownContainer"] h2,
            div[data-testid="stMarkdownContainer"] h3,
            div[data-testid="stMarkdownContainer"] h4,
            div[data-testid="stMarkdownContainer"] h5 {
                margin-top: 0.88rem !important;
                margin-bottom: 0.42rem !important;
            }

            div[data-testid="stFileUploader"] section {
                min-height: 88px !important;
                padding: 13px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
