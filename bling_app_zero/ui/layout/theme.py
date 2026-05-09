from __future__ import annotations

import streamlit as st


_THEME_ALREADY_INJECTED_KEY = 'bling_layout_theme_injected'


def inject_unified_light_layout(force: bool = False) -> None:
    """Tema maestro global limpo, leve e profissional."""
    if st.session_state.get(_THEME_ALREADY_INJECTED_KEY) and not force:
        return
    st.session_state[_THEME_ALREADY_INJECTED_KEY] = True

    st.markdown(
        """
        <style>
        :root {
            --bling-bg: #f6f9ff;
            --bling-panel: rgba(255, 255, 255, 0.96);
            --bling-panel-soft: rgba(248, 251, 255, 0.92);
            --bling-border: rgba(37, 99, 235, 0.14);
            --bling-text: #0f172a;
            --bling-muted: rgba(71, 85, 105, 0.78);
            --bling-primary: #2563eb;
            --bling-primary-dark: #1d4ed8;
            --bling-primary-soft: rgba(37, 99, 235, 0.10);
            --bling-accent: #38bdf8;
            --bling-success: #16a34a;
            --bling-warning: #ca8a04;
            --bling-danger: #dc2626;
            --bling-radius-xl: 24px;
            --bling-radius-lg: 18px;
            --bling-radius-md: 14px;
            --bling-radius-sm: 11px;
            --bling-shadow: 0 18px 48px rgba(37, 99, 235, 0.08);
            --bling-shadow-soft: 0 8px 22px rgba(15, 23, 42, 0.045);
            --bling-content-width: 980px;
        }

        html,
        body,
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"] {
            overflow-x: hidden !important;
            color: var(--bling-text) !important;
            background:
                radial-gradient(circle at 18% 0%, rgba(56, 189, 248, 0.16), transparent 24rem),
                radial-gradient(circle at 82% 0%, rgba(37, 99, 235, 0.12), transparent 26rem),
                linear-gradient(180deg, #ffffff 0%, var(--bling-bg) 52%, #ffffff 100%) !important;
            -webkit-font-smoothing: antialiased !important;
            text-rendering: optimizeLegibility !important;
        }

        header[data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.78) !important;
            border-bottom: 1px solid rgba(191, 219, 254, 0.55) !important;
            backdrop-filter: blur(14px) !important;
        }

        .main .block-container,
        .block-container {
            width: min(100%, var(--bling-content-width)) !important;
            max-width: var(--bling-content-width) !important;
            margin: 0 auto !important;
            padding: 4.6rem 1rem 2rem 1rem !important;
            box-sizing: border-box !important;
        }

        .main .block-container > div:first-child {
            margin-top: 0.85rem !important;
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-xl) !important;
            background: rgba(255, 255, 255, 0.70) !important;
            box-shadow: var(--bling-shadow) !important;
            padding: 1.25rem !important;
            overflow: visible !important;
        }

        .bling-hero,
        .bling-flow-card {
            width: min(100%, 720px) !important;
            margin: 0 auto 1rem auto !important;
            padding: 1.35rem 1.15rem 1.25rem 1.15rem !important;
            border: 1px solid rgba(37, 99, 235, 0.16) !important;
            border-radius: 22px !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(239,246,255,0.92)) !important;
            box-shadow: 0 14px 34px rgba(37, 99, 235, 0.08) !important;
            text-align: center !important;
            position: relative !important;
            overflow: hidden !important;
        }

        .bling-hero::before,
        .bling-flow-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--bling-primary), var(--bling-accent));
        }

        .bling-hero-kicker,
        .bling-flow-card-kicker {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 0 0.58rem 0 !important;
            padding: 0.28rem 0.62rem !important;
            border-radius: 999px !important;
            background: var(--bling-primary-soft) !important;
            border: 1px solid rgba(37, 99, 235, 0.13) !important;
            color: var(--bling-primary-dark) !important;
            font-size: 0.76rem !important;
            font-weight: 820 !important;
            line-height: 1.1 !important;
        }

        .bling-hero-title,
        .bling-flow-card-title {
            display: block !important;
            margin: 0 0 0.45rem 0 !important;
            color: var(--bling-text) !important;
            font-size: clamp(1.42rem, 3.6vw, 2.15rem) !important;
            font-weight: 920 !important;
            letter-spacing: -0.035em !important;
            line-height: 1.08 !important;
        }

        .bling-hero-subtitle,
        .bling-flow-card-text {
            display: block !important;
            margin: 0 auto !important;
            max-width: 560px !important;
            color: var(--bling-muted) !important;
            font-size: 0.96rem !important;
            line-height: 1.45 !important;
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
            width: min(100%, 760px) !important;
            padding: 1.1rem !important;
            margin: 0.8rem auto !important;
            text-align: center !important;
        }

        .bling-home-button-center {
            width: min(100%, 300px) !important;
            margin: 0.8rem auto 0 auto !important;
        }

        div[data-testid="stVerticalBlock"] { gap: 0.74rem !important; }
        div[data-testid="column"],
        div[data-testid="stElementContainer"],
        div[data-testid="stHorizontalBlock"] {
            max-width: 100% !important;
            box-sizing: border-box !important;
            overflow-x: hidden !important;
        }

        .bling-step-title,
        h1, h2, h3, h4, h5 {
            color: var(--bling-text) !important;
            font-weight: 880 !important;
            letter-spacing: -0.012em !important;
            line-height: 1.22 !important;
        }

        .bling-step-title {
            font-size: 1.16rem !important;
            position: relative !important;
            padding-left: 0.78rem !important;
            margin: 1rem 0 0.45rem 0 !important;
        }

        .bling-step-title::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0.3rem;
            width: 4px;
            height: 1.08rem;
            border-radius: 999px;
            background: linear-gradient(180deg, var(--bling-primary), var(--bling-accent));
        }

        .bling-muted,
        .bling-upload-caption,
        div[data-testid="stCaptionContainer"],
        div[data-testid="stMarkdownContainer"] p {
            color: var(--bling-muted) !important;
            line-height: 1.45 !important;
        }

        .bling-upload-title {
            margin: 1rem 0 0.25rem 0 !important;
            color: var(--bling-text) !important;
            font-size: 1rem !important;
            font-weight: 850 !important;
        }

        .bling-upload-caption {
            margin: 0 0 0.62rem 0 !important;
            font-size: 0.88rem !important;
        }

        .bling-home-pill,
        .bling-selected-flow-badge {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.42rem !important;
            color: var(--bling-primary-dark) !important;
            background: var(--bling-primary-soft) !important;
            border: 1px solid rgba(37, 99, 235, 0.14) !important;
            border-radius: 999px !important;
            padding: 0.34rem 0.68rem !important;
            font-size: 0.84rem !important;
            font-weight: 820 !important;
        }

        .bling-home-pill::before,
        .bling-selected-flow-dot {
            content: "";
            display: inline-block !important;
            width: 0.48rem !important;
            height: 0.48rem !important;
            border-radius: 999px !important;
            background: var(--bling-accent) !important;
            box-shadow: 0 0 0 5px rgba(56, 189, 248, 0.14) !important;
        }

        .bling-compact-note,
        .bling-inline-preview {
            border-radius: var(--bling-radius-sm) !important;
            padding: 0.6rem 0.7rem !important;
            background: rgba(239, 246, 255, 0.84) !important;
            color: rgba(30, 64, 175, 0.82) !important;
            border: 1px solid rgba(37, 99, 235, 0.12) !important;
            font-size: 0.88rem !important;
            line-height: 1.42 !important;
            margin: 0.55rem 0 0.75rem 0 !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFileUploader"] button {
            min-height: 44px !important;
            border-radius: 14px !important;
            border: 1px solid rgba(37, 99, 235, 0.18) !important;
            background: rgba(255, 255, 255, 0.96) !important;
            color: var(--bling-text) !important;
            box-shadow: 0 7px 18px rgba(15, 23, 42, 0.045) !important;
            font-weight: 780 !important;
            white-space: normal !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        div[data-testid="stFileUploader"] button:hover {
            border-color: rgba(37, 99, 235, 0.34) !important;
            background: rgba(239, 246, 255, 0.98) !important;
            box-shadow: 0 12px 26px rgba(37, 99, 235, 0.11) !important;
            transform: translateY(-1px) !important;
        }

        button[kind="primary"],
        .bling-primary-cta-anchor + div .stButton > button,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button {
            color: #ffffff !important;
            background: linear-gradient(135deg, var(--bling-primary), var(--bling-primary-dark)) !important;
            border-color: rgba(37, 99, 235, 0.34) !important;
            box-shadow: 0 14px 32px rgba(37, 99, 235, 0.24) !important;
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

        div[data-testid="stDataFrame"] {
            border-radius: var(--bling-radius-md) !important;
            overflow: hidden !important;
            border: 1px solid var(--bling-border) !important;
            background: #ffffff !important;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.035) !important;
        }

        section[data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.96) !important;
            border-right: 1px solid rgba(191, 219, 254, 0.72) !important;
        }

        #MainMenu,
        footer { visibility: hidden !important; }

        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                width: 100% !important;
                max-width: 100vw !important;
                padding: 3.2rem 0.82rem 1.2rem 0.82rem !important;
            }

            .main .block-container > div:first-child {
                margin-top: 0.65rem !important;
                padding: 0.9rem !important;
                border-radius: 22px !important;
                background: rgba(255, 255, 255, 0.62) !important;
                box-shadow: 0 14px 34px rgba(37, 99, 235, 0.07) !important;
            }

            .bling-hero,
            .bling-flow-card {
                width: 100% !important;
                margin: 0 auto 0.75rem auto !important;
                padding: 1.05rem 0.88rem 1rem 0.88rem !important;
                border-radius: 18px !important;
                box-shadow: 0 10px 24px rgba(37, 99, 235, 0.07) !important;
            }

            .bling-hero-kicker,
            .bling-flow-card-kicker {
                font-size: 0.68rem !important;
                margin-bottom: 0.48rem !important;
            }

            .bling-hero-title,
            .bling-flow-card-title {
                font-size: 1.34rem !important;
                line-height: 1.12 !important;
                letter-spacing: -0.025em !important;
                margin-bottom: 0.42rem !important;
            }

            .bling-hero-subtitle,
            .bling-flow-card-text {
                font-size: 0.84rem !important;
                line-height: 1.36 !important;
                max-width: 300px !important;
            }

            .bling-home-button-center {
                width: min(100%, 250px) !important;
                margin-top: 0.68rem !important;
            }

            .stButton > button,
            .stDownloadButton > button {
                min-height: 42px !important;
                font-size: 0.92rem !important;
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
