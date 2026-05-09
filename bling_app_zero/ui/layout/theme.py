from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.layout.components import inject_clean_home_css


def inject_unified_light_layout() -> None:
    """Tema global único, leve e centralizado."""
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
            --bling-primary: #b91c1c;
            --bling-primary-dark: #991b1b;
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
            -webkit-font-smoothing: antialiased !important;
            text-rendering: optimizeLegibility !important;
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
            padding: 4.7rem 0.82rem 1.4rem 0.82rem !important;
            box-sizing: border-box !important;
        }

        .main .block-container > div:first-child {
            border: 1px solid var(--bling-border) !important;
            border-radius: 24px !important;
            background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(248,250,252,0.84)) !important;
            box-shadow: var(--bling-shadow) !important;
            padding: 2.1rem 0.85rem 1.15rem 0.85rem !important;
            min-height: auto !important;
            overflow: visible !important;
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
            font-weight: 920 !important;
            letter-spacing: -0.01em !important;
            line-height: 1.18 !important;
            margin: 0 0 7px 0 !important;
            overflow-wrap: normal !important;
            word-break: normal !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.48rem !important;
            flex-wrap: wrap !important;
        }

        .bling-hero-icon {
            display: inline-flex !important;
            align-items: center !important;
            line-height: 1 !important;
        }

        .bling-hero-subtitle {
            color: var(--bling-muted) !important;
            font-size: 0.98rem !important;
            line-height: 1.42 !important;
            margin: 0 auto !important;
            max-width: 760px !important;
            overflow-wrap: normal !important;
            word-break: normal !important;
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
            margin: 0 auto 0.65rem auto !important;
        }

        .bling-home-card-start {
            text-align: center !important;
        }

        .bling-home-pill {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.35rem !important;
        }

        .bling-home-pill::before {
            content: "";
            display: inline-block;
            width: 0.45rem;
            height: 0.45rem;
            border-radius: 999px;
            background: var(--bling-primary);
            flex: 0 0 auto;
        }

        .bling-home-mini-step strong,
        .bling-home-mini-step span {
            white-space: normal !important;
            overflow-wrap: normal !important;
            word-break: keep-all !important;
        }

        .bling-primary-cta-anchor + div .stButton > button,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button {
            background: linear-gradient(135deg, var(--bling-primary), var(--bling-primary-dark)) !important;
            border: 1px solid rgba(127, 29, 29, 0.25) !important;
            color: #ffffff !important;
            box-shadow: 0 12px 26px rgba(185, 28, 28, 0.22) !important;
            font-weight: 900 !important;
            letter-spacing: 0.01em !important;
        }

        .bling-primary-cta-anchor + div .stButton > button:hover,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 16px 32px rgba(185, 28, 28, 0.28) !important;
            border-color: rgba(127, 29, 29, 0.42) !important;
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
            font-weight: 880 !important;
            letter-spacing: -0.006em !important;
            line-height: 1.24 !important;
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
            line-height: 1.42 !important;
            overflow-wrap: normal !important;
            word-break: normal !important;
        }

        .bling-upload-title {
            display: block !important;
            clear: both !important;
            margin: 1.02rem 0 0.22rem 0 !important;
            padding-top: 0.2rem !important;
            color: var(--bling-text) !important;
            font-size: 1.04rem !important;
            font-weight: 880 !important;
            letter-spacing: -0.004em !important;
            line-height: 1.28 !important;
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
            font-weight: 740 !important;
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
                --bling-flow-gap: 0.6rem;
                --bling-section-gap: 0.84rem;
            }

            .main .block-container,
            .block-container {
                width: 100% !important;
                max-width: 100vw !important;
                padding: 3.35rem 0.58rem 0.85rem 0.58rem !important;
            }

            .main .block-container > div:first-child {
                border-radius: 18px !important;
                padding: 0.78rem 0.58rem 0.82rem 0.58rem !important;
                min-height: auto !important;
                overflow: visible !important;
            }

            .bling-hero {
                border-radius: 14px !important;
                padding: 12px 11px !important;
                margin-bottom: 0.62rem !important;
            }

            .bling-hero-title {
                font-size: 1.22rem !important;
                letter-spacing: normal !important;
                line-height: 1.22 !important;
                gap: 0.36rem !important;
            }

            .bling-hero-subtitle {
                font-size: 0.84rem !important;
                line-height: 1.42 !important;
            }

            .bling-home-card {
                padding: 14px 11px !important;
                border-radius: 15px !important;
                margin-bottom: 0.45rem !important;
            }

            .bling-home-mini-steps {
                grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            }

            .bling-home-mini-step {
                min-height: 54px !important;
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
                margin-top: 0.82rem !important;
                margin-bottom: 0.38rem !important;
            }

            div[data-testid="stMarkdownContainer"] p,
            .bling-muted,
            .bling-upload-caption {
                line-height: 1.42 !important;
            }

            div[data-testid="stFileUploader"] section {
                min-height: 88px !important;
                padding: 13px !important;
            }
        }

        @media (max-width: 390px) {
            .main .block-container,
            .block-container {
                padding-left: 0.48rem !important;
                padding-right: 0.48rem !important;
            }

            .main .block-container > div:first-child {
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
            }

            .bling-home-mini-steps {
                gap: 0.42rem !important;
            }

            .bling-home-mini-step strong {
                font-size: 0.72rem !important;
            }

            .bling-home-mini-step span {
                font-size: 0.66rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_app_layout() -> None:
    inject_unified_light_layout()


__all__ = ['inject_app_layout', 'inject_clean_home_css', 'inject_unified_light_layout']
