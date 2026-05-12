from __future__ import annotations

import streamlit as st


def inject_unified_light_layout(force: bool = False) -> None:
    """Tema maestro global do sistema."""
    _ = force
    st.markdown(
        """
        <style id="bling-unified-theme">
        :root {
            --bling-bg: #f8fbff;
            --bling-surface: #ffffff;
            --bling-surface-soft: #f1f7ff;
            --bling-border: rgba(37, 99, 235, 0.14);
            --bling-text: #0f172a;
            --bling-muted: #64748b;
            --bling-primary: #2563eb;
            --bling-primary-dark: #1d4ed8;
            --bling-accent: #38bdf8;
            --bling-warning-bg: #fff7ed;
            --bling-warning-border: rgba(251, 146, 60, 0.42);
            --bling-warning-text: #7c2d12;
            --bling-radius-xl: 24px;
            --bling-radius-lg: 18px;
            --bling-shadow: 0 16px 42px rgba(15, 23, 42, 0.065);
            --bling-shadow-soft: 0 8px 22px rgba(15, 23, 42, 0.045);
            --bling-content-width: 980px;
        }

        html,
        body,
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"],
        .stApp {
            overflow-x: hidden !important;
            color: var(--bling-text) !important;
            background:
                radial-gradient(circle at 20% 0%, rgba(56, 189, 248, 0.13), transparent 22rem),
                radial-gradient(circle at 88% 2%, rgba(37, 99, 235, 0.10), transparent 28rem),
                linear-gradient(180deg, #ffffff 0%, var(--bling-bg) 100%) !important;
            -webkit-font-smoothing: antialiased !important;
            text-rendering: optimizeLegibility !important;
        }

        header[data-testid="stHeader"] {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 999999 !important;
            background: rgba(255, 255, 255, 0.82) !important;
            border-bottom: 1px solid rgba(226, 232, 240, 0.78) !important;
            backdrop-filter: blur(14px) !important;
        }

        div[data-testid="stToolbar"],
        div[data-testid="stToolbar"] *,
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        button[kind="header"],
        button[data-testid="collapsedControl"],
        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 1000000 !important;
        }

        .main .block-container,
        .block-container {
            width: min(100%, var(--bling-content-width)) !important;
            max-width: var(--bling-content-width) !important;
            margin: 0 auto !important;
            padding: 4.2rem 1rem 2rem 1rem !important;
            box-sizing: border-box !important;
        }

        .bling-hero,
        .bling-flow-card,
        .bling-inline-card {
            width: min(100%, 760px) !important;
            margin: 0 auto 1rem auto !important;
            padding: 1.25rem 1.15rem !important;
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-xl) !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,247,255,0.94)) !important;
            box-shadow: var(--bling-shadow) !important;
            text-align: left !important;
            position: relative !important;
            overflow: hidden !important;
        }

        .bling-model-card {
            margin-bottom: 0.55rem !important;
        }

        .bling-hero::before,
        .bling-flow-card::before,
        .bling-inline-card::before {
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
            margin: 0 0 0.62rem 0 !important;
            padding: 0.30rem 0.66rem !important;
            border-radius: 999px !important;
            background: rgba(37, 99, 235, 0.10) !important;
            border: 1px solid rgba(37, 99, 235, 0.12) !important;
            color: var(--bling-primary-dark) !important;
            font-size: 0.78rem !important;
            font-weight: 820 !important;
            line-height: 1.1 !important;
        }

        .bling-hero-title,
        .bling-flow-card-title {
            display: block !important;
            margin: 0 0 0.46rem 0 !important;
            color: var(--bling-text) !important;
            font-size: clamp(1.48rem, 3.6vw, 2.18rem) !important;
            font-weight: 920 !important;
            letter-spacing: -0.035em !important;
            line-height: 1.08 !important;
        }

        .bling-hero-subtitle,
        .bling-flow-card-text,
        .bling-muted,
        .bling-upload-caption,
        div[data-testid="stCaptionContainer"],
        div[data-testid="stMarkdownContainer"] p {
            color: var(--bling-muted) !important;
            line-height: 1.45 !important;
        }

        div[data-testid="stVerticalBlock"] { gap: 0.82rem !important; }
        div[data-testid="column"],
        div[data-testid="stElementContainer"],
        div[data-testid="stHorizontalBlock"] {
            max-width: 100% !important;
            box-sizing: border-box !important;
            overflow-x: hidden !important;
        }

        .bling-home-button-center {
            width: min(100%, 300px) !important;
            margin: 0.8rem auto 0 auto !important;
        }

        .bling-step-title,
        h1, h2, h3, h4, h5 {
            color: var(--bling-text) !important;
            font-weight: 880 !important;
            letter-spacing: -0.012em !important;
            line-height: 1.22 !important;
        }

        .bling-selected-flow-badge,
        .bling-home-pill {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.42rem !important;
            color: var(--bling-primary-dark) !important;
            background: rgba(37, 99, 235, 0.10) !important;
            border: 1px solid rgba(37, 99, 235, 0.14) !important;
            border-radius: 999px !important;
            padding: 0.34rem 0.68rem !important;
            font-size: 0.84rem !important;
            font-weight: 820 !important;
            margin: 0 0 0.8rem 0 !important;
        }

        .bling-compact-note,
        .bling-inline-preview {
            border-radius: 12px !important;
            padding: 0.62rem 0.72rem !important;
            background: rgba(239, 246, 255, 0.88) !important;
            color: rgba(30, 64, 175, 0.85) !important;
            border: 1px solid rgba(37, 99, 235, 0.12) !important;
            font-size: 0.88rem !important;
            line-height: 1.42 !important;
            margin: 0.55rem 0 0.75rem 0 !important;
        }

        .stAlert,
        div[data-testid="stAlert"] {
            border-radius: 16px !important;
            box-shadow: none !important;
        }

        div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]),
        .stAlert:has([data-testid="stAlertContentWarning"]) {
            background: var(--bling-warning-bg) !important;
            border: 1px solid var(--bling-warning-border) !important;
            color: var(--bling-warning-text) !important;
        }

        div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) *,
        .stAlert:has([data-testid="stAlertContentWarning"]) * {
            color: var(--bling-warning-text) !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFileUploader"] button {
            min-height: 44px !important;
            border-radius: 14px !important;
            border: 1px solid rgba(37, 99, 235, 0.18) !important;
            background: #ffffff !important;
            color: var(--bling-text) !important;
            box-shadow: 0 6px 16px rgba(15, 23, 42, 0.045) !important;
            font-weight: 780 !important;
            white-space: normal !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        div[data-testid="stFileUploader"] button:hover {
            border-color: rgba(37, 99, 235, 0.34) !important;
            background: var(--bling-surface-soft) !important;
            box-shadow: 0 10px 22px rgba(37, 99, 235, 0.10) !important;
            transform: translateY(-1px) !important;
        }

        .stButton > button:disabled,
        .stButton > button[disabled],
        .stDownloadButton > button:disabled,
        .stDownloadButton > button[disabled] {
            cursor: default !important;
            opacity: 0.72 !important;
            color: #94a3b8 !important;
            background: rgba(248, 250, 252, 0.82) !important;
            border: 1px solid rgba(203, 213, 225, 0.72) !important;
            box-shadow: none !important;
            transform: none !important;
        }

        button[kind="primary"],
        .bling-primary-cta-anchor + div .stButton > button,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button {
            color: #ffffff !important;
            background: linear-gradient(135deg, var(--bling-primary), var(--bling-primary-dark)) !important;
            border-color: rgba(37, 99, 235, 0.34) !important;
            box-shadow: 0 12px 28px rgba(37, 99, 235, 0.22) !important;
        }

        div[data-testid="stFileUploader"] {
            width: min(100%, 760px) !important;
            margin: 0 auto 1rem auto !important;
        }

        div[data-testid="stFileUploader"] section {
            border: 1px dashed rgba(37, 99, 235, 0.22) !important;
            border-radius: var(--bling-radius-xl) !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,247,255,0.94)) !important;
            box-shadow: var(--bling-shadow-soft) !important;
            padding: 1rem !important;
            min-height: 118px !important;
        }

        input,
        textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            border-radius: 14px !important;
            background: #ffffff !important;
            border-color: rgba(37, 99, 235, 0.16) !important;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 16px !important;
            overflow: hidden !important;
            border: 1px solid var(--bling-border) !important;
            background: #ffffff !important;
            box-shadow: var(--bling-shadow-soft) !important;
        }

        section[data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.96) !important;
            border-right: 1px solid rgba(191, 219, 254, 0.72) !important;
        }

        footer { visibility: hidden !important; }

        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                width: 100% !important;
                max-width: 100vw !important;
                padding: 3.15rem 0.9rem 1.2rem 0.9rem !important;
            }

            .bling-hero,
            .bling-flow-card,
            .bling-inline-card,
            div[data-testid="stFileUploader"] {
                width: 100% !important;
                margin: 0 0 0.78rem 0 !important;
            }

            .bling-hero,
            .bling-flow-card,
            .bling-inline-card {
                padding: 1rem 0.92rem !important;
                border-radius: 20px !important;
                text-align: left !important;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.055) !important;
            }

            .bling-hero-kicker,
            .bling-flow-card-kicker {
                font-size: 0.68rem !important;
                margin-bottom: 0.52rem !important;
            }

            .bling-hero-title,
            .bling-flow-card-title {
                font-size: 1.42rem !important;
                line-height: 1.12 !important;
                letter-spacing: -0.026em !important;
                margin-bottom: 0.46rem !important;
            }

            .bling-hero-subtitle,
            .bling-flow-card-text {
                font-size: 0.86rem !important;
                line-height: 1.38 !important;
                max-width: 100% !important;
            }

            .bling-home-button-center {
                width: min(100%, 260px) !important;
                margin-top: 0.68rem !important;
            }

            div[data-testid="stFileUploader"] section {
                min-height: 110px !important;
                padding: 0.9rem !important;
                border-radius: 20px !important;
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
