from __future__ import annotations

import streamlit as st


def inject_unified_light_layout(force: bool = False) -> None:
    """Tema maestro global do sistema."""
    _ = force
    st.markdown(
        """
        <style id="bling-unified-theme">
        :root {
            --bling-bg: #f7f8fc;
            --bling-bg-soft: #eef2f8;
            --bling-surface: #ffffff;
            --bling-surface-soft: #f3f6fb;
            --bling-surface-green: #eaf7f0;
            --bling-border: rgba(71, 85, 105, 0.16);
            --bling-border-strong: rgba(71, 85, 105, 0.26);
            --bling-text: #1f2937;
            --bling-text-soft: #334155;
            --bling-muted: #64748b;
            --bling-primary: #4f67a5;
            --bling-primary-dark: #40588f;
            --bling-primary-hover: #3b5184;
            --bling-primary-soft: #edf2ff;
            --bling-accent: #6f86bf;
            --bling-success-bg: #eaf7f0;
            --bling-success-border: rgba(34, 197, 94, 0.18);
            --bling-success-text: #475569;
            --bling-warning-bg: #fff7ed;
            --bling-warning-border: rgba(251, 146, 60, 0.42);
            --bling-warning-text: #7c2d12;
            --bling-radius-xl: 22px;
            --bling-radius-lg: 16px;
            --bling-radius-md: 12px;
            --bling-shadow: 0 14px 34px rgba(15, 23, 42, 0.070);
            --bling-shadow-soft: 0 7px 18px rgba(15, 23, 42, 0.050);
            --bling-content-width: 980px;
            --bling-font-family: Inter, "Segoe UI", Roboto, Arial, sans-serif;
        }

        html,
        body,
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"],
        .stApp {
            overflow-x: hidden !important;
            color: var(--bling-text) !important;
            background:
                radial-gradient(circle at 16% 0%, rgba(79, 103, 165, 0.10), transparent 24rem),
                radial-gradient(circle at 92% 4%, rgba(111, 134, 191, 0.09), transparent 26rem),
                linear-gradient(180deg, #ffffff 0%, var(--bling-bg) 100%) !important;
            font-family: var(--bling-font-family) !important;
            -webkit-font-smoothing: antialiased !important;
            text-rendering: optimizeLegibility !important;
        }

        html *,
        body *,
        [data-testid="stApp"] * {
            font-family: var(--bling-font-family) !important;
        }

        header[data-testid="stHeader"] {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 999999 !important;
            background: rgba(255, 255, 255, 0.86) !important;
            border-bottom: 1px solid rgba(226, 232, 240, 0.88) !important;
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
        .bling-inline-card,
        div[data-testid="stForm"],
        div[data-testid="stExpander"] {
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-xl) !important;
            background: rgba(255, 255, 255, 0.96) !important;
            box-shadow: var(--bling-shadow-soft) !important;
        }

        .bling-hero,
        .bling-flow-card,
        .bling-inline-card {
            width: min(100%, 760px) !important;
            margin: 0 auto 1rem auto !important;
            padding: 1.25rem 1.15rem !important;
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
        .bling-flow-card-kicker,
        .bling-selected-flow-badge,
        .bling-home-pill {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.42rem !important;
            color: var(--bling-primary-dark) !important;
            background: var(--bling-primary-soft) !important;
            border: 1px solid rgba(79, 103, 165, 0.16) !important;
            border-radius: 999px !important;
            padding: 0.34rem 0.68rem !important;
            font-size: 0.82rem !important;
            font-weight: 820 !important;
            line-height: 1.1 !important;
            margin: 0 0 0.78rem 0 !important;
        }

        .bling-hero-title,
        .bling-flow-card-title,
        .bling-step-title,
        h1, h2, h3, h4, h5 {
            display: block !important;
            color: var(--bling-text) !important;
            font-weight: 880 !important;
            letter-spacing: -0.018em !important;
            line-height: 1.16 !important;
        }

        .bling-hero-title,
        .bling-flow-card-title {
            margin: 0 0 0.46rem 0 !important;
            font-size: clamp(1.42rem, 3.4vw, 2.06rem) !important;
        }

        .bling-hero-subtitle,
        .bling-flow-card-text,
        .bling-muted,
        .bling-upload-caption,
        div[data-testid="stCaptionContainer"],
        div[data-testid="stMarkdownContainer"] p {
            color: var(--bling-muted) !important;
            line-height: 1.45 !important;
            font-weight: 500 !important;
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

        .bling-compact-note,
        .bling-inline-preview {
            border-radius: var(--bling-radius-md) !important;
            padding: 0.68rem 0.78rem !important;
            background: var(--bling-primary-soft) !important;
            color: var(--bling-text-soft) !important;
            border: 1px solid rgba(79, 103, 165, 0.14) !important;
            font-size: 0.9rem !important;
            line-height: 1.42 !important;
            margin: 0.55rem 0 0.75rem 0 !important;
        }

        .stAlert,
        div[data-testid="stAlert"] {
            border-radius: 16px !important;
            box-shadow: none !important;
        }

        div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]),
        .stAlert:has([data-testid="stAlertContentSuccess"]) {
            background: var(--bling-success-bg) !important;
            border: 1px solid var(--bling-success-border) !important;
            color: var(--bling-success-text) !important;
        }

        div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) *,
        .stAlert:has([data-testid="stAlertContentSuccess"]) * {
            color: var(--bling-success-text) !important;
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
        div[data-testid="stFileUploader"] button,
        button[kind="secondary"] {
            min-height: 46px !important;
            border-radius: 18px !important;
            border: 1px solid var(--bling-border-strong) !important;
            background: #ffffff !important;
            color: var(--bling-text-soft) !important;
            box-shadow: 0 5px 14px rgba(15, 23, 42, 0.045) !important;
            font-weight: 760 !important;
            letter-spacing: 0.005em !important;
            white-space: normal !important;
            transition: background .16s ease, border-color .16s ease, box-shadow .16s ease, transform .16s ease !important;
        }

        .stButton > button *,
        .stDownloadButton > button *,
        div[data-testid="stFileUploader"] button *,
        button[kind="secondary"] * {
            color: inherit !important;
            font-weight: inherit !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        div[data-testid="stFileUploader"] button:hover,
        button[kind="secondary"]:hover {
            border-color: rgba(79, 103, 165, 0.42) !important;
            background: var(--bling-primary-soft) !important;
            box-shadow: 0 8px 20px rgba(79, 103, 165, 0.12) !important;
            transform: translateY(-1px) !important;
            color: var(--bling-primary-dark) !important;
        }

        .stButton > button:focus,
        .stDownloadButton > button:focus,
        div[data-testid="stFileUploader"] button:focus,
        button[kind="secondary"]:focus {
            outline: 3px solid rgba(79, 103, 165, 0.18) !important;
            outline-offset: 2px !important;
            box-shadow: 0 0 0 1px rgba(79, 103, 165, 0.18), 0 8px 20px rgba(79, 103, 165, 0.12) !important;
        }

        .stButton > button:disabled,
        .stButton > button[disabled],
        .stDownloadButton > button:disabled,
        .stDownloadButton > button[disabled],
        button:disabled,
        button[disabled] {
            cursor: not-allowed !important;
            opacity: 0.58 !important;
            color: #64748b !important;
            background: #eef2f7 !important;
            border: 1px solid rgba(148, 163, 184, 0.38) !important;
            box-shadow: none !important;
            transform: none !important;
        }

        .stButton > button:disabled *,
        .stButton > button[disabled] *,
        .stDownloadButton > button:disabled *,
        .stDownloadButton > button[disabled] *,
        button:disabled *,
        button[disabled] * {
            color: inherit !important;
        }

        button[kind="primary"],
        .bling-primary-cta-anchor + div .stButton > button,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button {
            color: #ffffff !important;
            background: linear-gradient(135deg, var(--bling-primary), var(--bling-primary-dark)) !important;
            border-color: rgba(64, 88, 143, 0.42) !important;
            box-shadow: 0 12px 26px rgba(64, 88, 143, 0.25) !important;
            font-weight: 820 !important;
        }

        button[kind="primary"] *,
        .bling-primary-cta-anchor + div .stButton > button *,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button * {
            color: #ffffff !important;
            font-weight: inherit !important;
        }

        button[kind="primary"]:hover,
        .bling-primary-cta-anchor + div .stButton > button:hover,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button:hover {
            color: #ffffff !important;
            background: linear-gradient(135deg, var(--bling-primary-dark), var(--bling-primary-hover)) !important;
            border-color: rgba(59, 81, 132, 0.50) !important;
            box-shadow: 0 14px 30px rgba(64, 88, 143, 0.30) !important;
        }

        button[kind="primary"]:hover *,
        .bling-primary-cta-anchor + div .stButton > button:hover *,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button:hover * {
            color: #ffffff !important;
        }

        div[data-testid="stFileUploader"] {
            width: min(100%, 760px) !important;
            margin: 0 auto 1rem auto !important;
        }

        div[data-testid="stFileUploader"] section {
            border: 1px dashed rgba(79, 103, 165, 0.26) !important;
            border-radius: var(--bling-radius-xl) !important;
            background: rgba(255, 255, 255, 0.94) !important;
            box-shadow: var(--bling-shadow-soft) !important;
            padding: 1rem !important;
            min-height: 118px !important;
        }

        input,
        textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            border-radius: 16px !important;
            background: #ffffff !important;
            border-color: var(--bling-border-strong) !important;
            color: var(--bling-text) !important;
        }

        input::placeholder,
        textarea::placeholder {
            color: #94a3b8 !important;
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
            border-right: 1px solid rgba(203, 213, 225, 0.82) !important;
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
            .bling-flow-card-kicker,
            .bling-selected-flow-badge,
            .bling-home-pill {
                font-size: 0.70rem !important;
                margin-bottom: 0.52rem !important;
            }

            .bling-hero-title,
            .bling-flow-card-title {
                font-size: 1.38rem !important;
                line-height: 1.12 !important;
                letter-spacing: -0.026em !important;
                margin-bottom: 0.46rem !important;
            }

            .bling-hero-subtitle,
            .bling-flow-card-text {
                font-size: 0.88rem !important;
                line-height: 1.40 !important;
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
            .stDownloadButton > button,
            div[data-testid="stFileUploader"] button,
            button[kind="primary"],
            button[kind="secondary"] {
                min-height: 46px !important;
                font-size: 0.94rem !important;
                border-radius: 18px !important;
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
