from __future__ import annotations

import streamlit as st


_THEME_ALREADY_INJECTED_KEY = 'bling_layout_theme_injected'


def inject_unified_light_layout(force: bool = False) -> None:
    """Tema maestro global do sistema.

    Este arquivo deve ser o unico responsavel por cores, respiros, cards,
    botoes, inputs, tabelas e comportamento visual base. Qualquer tela que
    chamar inject_app_layout passa a herdar o mesmo design.
    """
    if st.session_state.get(_THEME_ALREADY_INJECTED_KEY) and not force:
        return
    st.session_state[_THEME_ALREADY_INJECTED_KEY] = True

    st.markdown(
        """
        <style>
        :root {
            --bling-bg: #f6f9ff;
            --bling-bg-strong: #eef6ff;
            --bling-panel: rgba(255, 255, 255, 0.88);
            --bling-panel-strong: rgba(255, 255, 255, 0.97);
            --bling-panel-soft: rgba(248, 251, 255, 0.82);
            --bling-border: rgba(37, 99, 235, 0.14);
            --bling-border-soft: rgba(15, 23, 42, 0.075);
            --bling-text: #0f172a;
            --bling-muted: rgba(51, 65, 85, 0.72);
            --bling-primary: #2563eb;
            --bling-primary-dark: #1d4ed8;
            --bling-primary-soft: rgba(37, 99, 235, 0.10);
            --bling-accent: #38bdf8;
            --bling-success: #16a34a;
            --bling-warning: #ca8a04;
            --bling-danger: #dc2626;
            --bling-shadow: 0 24px 70px rgba(37, 99, 235, 0.09);
            --bling-shadow-soft: 0 12px 34px rgba(15, 23, 42, 0.055);
            --bling-radius-xl: 28px;
            --bling-radius-lg: 22px;
            --bling-radius-md: 16px;
            --bling-radius-sm: 12px;
            --bling-flow-gap: 0.9rem;
            --bling-section-gap: 1.15rem;
            --bling-content-width: 1060px;
            --bling-card-width: 860px;
        }

        html,
        body,
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"] {
            color: var(--bling-text) !important;
            overflow-x: hidden !important;
            -webkit-font-smoothing: antialiased !important;
            text-rendering: optimizeLegibility !important;
            background:
                radial-gradient(circle at 20% 0%, rgba(56, 189, 248, 0.18), transparent 28rem),
                radial-gradient(circle at 78% 0%, rgba(37, 99, 235, 0.13), transparent 34rem),
                linear-gradient(180deg, #ffffff 0%, var(--bling-bg) 44%, #ffffff 100%) !important;
        }

        header[data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.72) !important;
            backdrop-filter: blur(16px) !important;
            border-bottom: 1px solid rgba(191, 219, 254, 0.62) !important;
        }

        .main .block-container,
        .block-container {
            width: min(100%, var(--bling-content-width)) !important;
            max-width: var(--bling-content-width) !important;
            margin: 0 auto !important;
            padding: 5.45rem 0.95rem 2.15rem 0.95rem !important;
            box-sizing: border-box !important;
            overflow: visible !important;
        }

        .main .block-container > div:first-child {
            margin-top: 1.1rem !important;
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-xl) !important;
            background: linear-gradient(180deg, rgba(255,255,255,0.80), rgba(248,251,255,0.74)) !important;
            box-shadow: var(--bling-shadow) !important;
            padding: 1.55rem 1.05rem 1.18rem 1.05rem !important;
            min-height: auto !important;
            overflow: visible !important;
        }

        .bling-hero {
            width: min(100%, var(--bling-card-width)) !important;
            margin: 1.15rem auto 1.2rem auto !important;
            padding: 20px 22px 18px 22px !important;
            border: 1px solid rgba(37, 99, 235, 0.16) !important;
            border-radius: 22px !important;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.96), rgba(239,246,255,0.86)) !important;
            box-shadow: 0 18px 50px rgba(37, 99, 235, 0.085) !important;
            text-align: center !important;
            position: relative !important;
            overflow: hidden !important;
        }

        .bling-hero::before {
            content: "";
            position: absolute;
            inset: 0 auto auto 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, var(--bling-primary), var(--bling-accent), rgba(37,99,235,0.15));
        }

        .bling-hero-title {
            color: var(--bling-text) !important;
            font-size: clamp(1.55rem, 3.4vw, 2.25rem) !important;
            font-weight: 920 !important;
            letter-spacing: -0.025em !important;
            line-height: 1.13 !important;
            margin: 0 0 0.45rem 0 !important;
            overflow-wrap: normal !important;
            word-break: normal !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.55rem !important;
            flex-wrap: wrap !important;
        }

        .bling-hero-subtitle {
            color: var(--bling-muted) !important;
            font-size: 0.98rem !important;
            line-height: 1.48 !important;
            margin: 0 auto !important;
            max-width: 720px !important;
        }

        .bling-home-center,
        div[data-testid="stHorizontalBlock"] {
            width: 100% !important;
            box-sizing: border-box !important;
        }

        .bling-home-card,
        div[data-testid="stExpander"] details,
        div[data-testid="stFileUploader"] section,
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-lg) !important;
            background: var(--bling-panel) !important;
            box-shadow: var(--bling-shadow-soft) !important;
        }

        .bling-home-card {
            width: min(100%, 780px) !important;
            padding: 22px !important;
            margin: 1rem auto 0.85rem auto !important;
        }

        .bling-home-card-start {
            text-align: center !important;
        }

        .bling-home-button-center {
            width: min(100%, 320px) !important;
            margin: 1.2rem auto 0 auto !important;
        }

        .bling-home-pill {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.4rem !important;
            color: var(--bling-primary-dark) !important;
            background: var(--bling-primary-soft) !important;
            border: 1px solid rgba(37, 99, 235, 0.14) !important;
            border-radius: 999px !important;
            padding: 0.32rem 0.62rem !important;
            font-weight: 820 !important;
        }

        .bling-home-pill::before {
            content: "";
            display: inline-block;
            width: 0.48rem;
            height: 0.48rem;
            border-radius: 999px;
            background: var(--bling-accent);
            box-shadow: 0 0 0 5px rgba(56, 189, 248, 0.14);
            flex: 0 0 auto;
        }

        .bling-primary-cta-anchor + div .stButton > button,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button,
        button[kind="primary"] {
            background: linear-gradient(135deg, var(--bling-primary), var(--bling-primary-dark)) !important;
            border: 1px solid rgba(37, 99, 235, 0.28) !important;
            color: #ffffff !important;
            box-shadow: 0 14px 32px rgba(37, 99, 235, 0.25) !important;
            font-weight: 900 !important;
            letter-spacing: 0.01em !important;
        }

        .bling-primary-cta-anchor + div .stButton > button:hover,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button:hover,
        button[kind="primary"]:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 18px 38px rgba(37, 99, 235, 0.32) !important;
        }

        div[data-testid="column"] {
            min-width: 0 !important;
            padding: 0 0.3rem !important;
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
            font-weight: 880 !important;
            letter-spacing: -0.012em !important;
            line-height: 1.22 !important;
            overflow-wrap: normal !important;
            word-break: normal !important;
        }

        .bling-step-title,
        div[data-testid="stMarkdownContainer"] h1,
        div[data-testid="stMarkdownContainer"] h2,
        div[data-testid="stMarkdownContainer"] h3,
        div[data-testid="stMarkdownContainer"] h4,
        div[data-testid="stMarkdownContainer"] h5 {
            display: block !important;
            clear: both !important;
            padding-top: 0.22rem !important;
            margin-top: var(--bling-section-gap) !important;
            margin-bottom: 0.48rem !important;
        }

        .bling-step-title {
            font-size: 1.2rem !important;
            position: relative !important;
            padding-left: 0.82rem !important;
        }

        .bling-step-title::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0.36rem;
            width: 4px;
            height: 1.05rem;
            border-radius: 999px;
            background: linear-gradient(180deg, var(--bling-primary), var(--bling-accent));
        }

        .bling-muted,
        .bling-upload-caption,
        div[data-testid="stCaptionContainer"],
        div[data-testid="stMarkdownContainer"] p {
            color: var(--bling-muted) !important;
            line-height: 1.48 !important;
            overflow-wrap: normal !important;
            word-break: normal !important;
        }

        .bling-upload-title {
            display: block !important;
            clear: both !important;
            margin: 1.05rem 0 0.24rem 0 !important;
            padding-top: 0.2rem !important;
            color: var(--bling-text) !important;
            font-size: 1.04rem !important;
            font-weight: 880 !important;
            letter-spacing: -0.004em !important;
            line-height: 1.28 !important;
        }

        .bling-upload-caption {
            display: block !important;
            margin: 0 0 0.62rem 0 !important;
            font-size: 0.9rem !important;
        }

        .bling-compact-note {
            border-radius: var(--bling-radius-sm) !important;
            padding: 10px 12px !important;
            background: rgba(239, 246, 255, 0.84) !important;
            color: rgba(30, 64, 175, 0.82) !important;
            border: 1px solid rgba(37, 99, 235, 0.12) !important;
            font-size: 0.9rem !important;
            line-height: 1.42 !important;
            margin: 0.55rem 0 0.75rem 0 !important;
        }

        .stAlert {
            border-radius: var(--bling-radius-sm) !important;
            border: 1px solid rgba(37, 99, 235, 0.10) !important;
            margin: 0.48rem 0 0.78rem 0 !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFileUploader"] button {
            border-radius: 14px !important;
            min-height: 44px !important;
            border: 1px solid rgba(37, 99, 235, 0.16) !important;
            background: rgba(255, 255, 255, 0.94) !important;
            color: var(--bling-text) !important;
            box-shadow: 0 7px 18px rgba(15, 23, 42, 0.045) !important;
            font-weight: 780 !important;
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease, background 120ms ease !important;
            white-space: normal !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        div[data-testid="stFileUploader"] button:hover {
            transform: translateY(-1px) !important;
            border-color: rgba(37, 99, 235, 0.32) !important;
            background: rgba(239, 246, 255, 0.98) !important;
            box-shadow: 0 12px 26px rgba(37, 99, 235, 0.11) !important;
        }

        div[data-testid="stFileUploader"] {
            margin: 0.45rem 0 0.85rem 0 !important;
        }

        div[data-testid="stFileUploader"] section {
            padding: 18px !important;
            min-height: 102px !important;
        }

        input,
        textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            border-radius: 14px !important;
            background: rgba(255, 255, 255, 0.96) !important;
            border-color: rgba(37, 99, 235, 0.15) !important;
        }

        input:focus,
        textarea:focus,
        div[data-baseweb="select"] > div:focus-within,
        div[data-baseweb="input"] > div:focus-within,
        div[data-baseweb="textarea"] > div:focus-within {
            border-color: rgba(37, 99, 235, 0.42) !important;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.09) !important;
        }

        div[data-testid="stTextArea"],
        div[data-testid="stTextInput"],
        div[data-testid="stSelectbox"],
        div[data-testid="stNumberInput"],
        div[data-testid="stRadio"] {
            margin: 0.18rem 0 0.58rem 0 !important;
        }

        div[data-testid="stDataFrame"] {
            border-radius: var(--bling-radius-md) !important;
            overflow: hidden !important;
            border: 1px solid var(--bling-border) !important;
            background: #ffffff !important;
            margin: 0.55rem 0 0.75rem 0 !important;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.035) !important;
        }

        div[data-testid="stExpander"] {
            margin: 0.72rem 0 0.88rem 0 !important;
        }

        div[data-testid="stExpander"] details summary {
            padding: 0.76rem 0.9rem !important;
            color: var(--bling-text) !important;
            font-weight: 780 !important;
        }

        section[data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.95) !important;
            border-right: 1px solid rgba(191, 219, 254, 0.72) !important;
        }

        .bling-tech-button-slot {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }

        .bling-tech-button-slot .stButton > button {
            min-height: 30px !important;
            height: 30px !important;
            width: 30px !important;
            border-radius: 999px !important;
            padding: 0 !important;
            font-size: 0.76rem !important;
            opacity: 0.82;
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
                padding: 4.15rem 0.66rem 1.05rem 0.66rem !important;
            }

            .main .block-container > div:first-child {
                margin-top: 0.85rem !important;
                border-radius: 20px !important;
                padding: 0.92rem 0.68rem 0.92rem 0.68rem !important;
            }

            .bling-hero {
                border-radius: 18px !important;
                padding: 15px 13px 14px 13px !important;
                margin: 0.95rem auto 0.82rem auto !important;
            }

            .bling-hero-title {
                font-size: 1.24rem !important;
                letter-spacing: -0.01em !important;
                line-height: 1.18 !important;
                gap: 0.34rem !important;
            }

            .bling-hero-subtitle {
                font-size: 0.84rem !important;
                line-height: 1.42 !important;
            }

            .bling-home-card {
                width: 100% !important;
                padding: 15px 12px !important;
                border-radius: 17px !important;
                margin: 0.86rem auto 0.55rem auto !important;
            }

            .bling-home-mini-steps {
                grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
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
                letter-spacing: normal !important;
                line-height: 1.26 !important;
                margin-top: 0.9rem !important;
                margin-bottom: 0.4rem !important;
            }

            div[data-testid="stFileUploader"] section {
                min-height: 90px !important;
                padding: 14px !important;
            }
        }

        @media (max-width: 390px) {
            .main .block-container,
            .block-container {
                padding-left: 0.52rem !important;
                padding-right: 0.52rem !important;
            }

            .main .block-container > div:first-child {
                padding-left: 0.54rem !important;
                padding-right: 0.54rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_app_layout(force: bool = False) -> None:
    inject_unified_light_layout(force=force)


def inject_clean_home_css() -> None:
    inject_app_layout()


__all__ = ['inject_app_layout', 'inject_clean_home_css', 'inject_unified_light_layout']
