from __future__ import annotations

import streamlit as st


def inject_unified_light_layout(force: bool = False) -> None:
    """Tema mestre global do sistema.

    Regra do projeto: nenhum outro arquivo deve criar tema próprio ou injetar CSS.
    Todo visual global deve ser centralizado aqui.
    """
    _ = force
    st.markdown(
        """
        <style id="bling-unified-theme">
        :root {
            --bling-bg: #f7f8fc;
            --bling-bg-soft: #eef2f8;
            --bling-surface: #ffffff;
            --bling-surface-soft: #f3f6fb;
            --bling-surface-warm: #fffaf5;
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
            --bling-danger-bg: #fef2f2;
            --bling-danger-border: rgba(248, 113, 113, 0.42);
            --bling-danger-text: #7f1d1d;
            --bling-success-bg: #eaf7f0;
            --bling-success-border: rgba(34, 197, 94, 0.22);
            --bling-success-text: #14532d;
            --bling-warning-bg: #fff7ed;
            --bling-warning-border: rgba(251, 146, 60, 0.42);
            --bling-warning-text: #7c2d12;
            --bling-info-bg: #eff6ff;
            --bling-info-border: rgba(79, 103, 165, 0.22);
            --bling-info-text: #40588f;
            --bling-radius-xl: 22px;
            --bling-radius-lg: 16px;
            --bling-radius-md: 12px;
            --bling-shadow: 0 14px 34px rgba(15, 23, 42, 0.070);
            --bling-shadow-soft: 0 7px 18px rgba(15, 23, 42, 0.050);
            --bling-content-width: 920px;
            --bling-card-width: 760px;
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

        html *, body *, [data-testid="stApp"] * {
            font-family: var(--bling-font-family) !important;
            box-sizing: border-box !important;
        }

        header[data-testid="stHeader"] {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 999999 !important;
            background: rgba(255, 255, 255, 0.88) !important;
            border-bottom: 1px solid rgba(226, 232, 240, 0.88) !important;
            backdrop-filter: blur(14px) !important;
        }

        div[data-testid="stToolbar"],
        div[data-testid="stToolbar"] *,
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        button[kind="header"],
        button[data-testid="collapsedControl"],
        [data-testid="collapsedControl"],
        #MainMenu {
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
            padding: 3.55rem 1rem 1.4rem 1rem !important;
        }

        div[data-testid="stVerticalBlock"] { gap: 0.62rem !important; }
        div[data-testid="column"],
        div[data-testid="stElementContainer"],
        div[data-testid="stHorizontalBlock"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
        }

        h1, h2, h3, h4, h5,
        .bling-hero-title,
        .bling-flow-card-title,
        .bling-step-title,
        .bling-wizard-progress-title {
            color: var(--bling-text) !important;
            font-weight: 880 !important;
            letter-spacing: -0.022em !important;
            line-height: 1.12 !important;
            margin-bottom: 0.35rem !important;
        }

        h1 { font-size: clamp(1.62rem, 4vw, 2.25rem) !important; }
        h2 { font-size: clamp(1.34rem, 3.3vw, 1.86rem) !important; }
        h3 { font-size: clamp(1.10rem, 2.9vw, 1.42rem) !important; }
        h4 { font-size: 1.02rem !important; }

        .bling-hero,
        .bling-flow-card,
        .bling-inline-card,
        .bling-model-card,
        div[data-testid="stForm"],
        div[data-testid="stExpander"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-xl) !important;
            background: rgba(255, 255, 255, 0.96) !important;
            box-shadow: var(--bling-shadow-soft) !important;
        }

        .bling-hero,
        .bling-flow-card,
        .bling-inline-card {
            width: min(100%, var(--bling-card-width)) !important;
            margin: 0 auto 0.72rem auto !important;
            padding: 1rem 1rem !important;
            text-align: left !important;
            position: relative !important;
            overflow: hidden !important;
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
        .bling-home-pill,
        .bling-wizard-progress-kicker {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 0.36rem !important;
            color: var(--bling-primary-dark) !important;
            background: var(--bling-primary-soft) !important;
            border: 1px solid rgba(79, 103, 165, 0.16) !important;
            border-radius: 999px !important;
            padding: 0.26rem 0.58rem !important;
            font-size: 0.74rem !important;
            font-weight: 820 !important;
            line-height: 1.1 !important;
            margin: 0 0 0.45rem 0 !important;
        }

        .bling-hero-title,
        .bling-flow-card-title {
            margin: 0 0 0.35rem 0 !important;
            font-size: clamp(1.32rem, 3.2vw, 1.92rem) !important;
        }

        .bling-hero-subtitle,
        .bling-flow-card-text,
        .bling-muted,
        .bling-upload-caption,
        div[data-testid="stCaptionContainer"],
        div[data-testid="stMarkdownContainer"] p {
            color: var(--bling-muted) !important;
            line-height: 1.34 !important;
            font-weight: 520 !important;
        }

        .bling-compact-note,
        .bling-inline-preview,
        .bling-map-preview {
            border-radius: var(--bling-radius-md) !important;
            padding: 0.58rem 0.68rem !important;
            background: var(--bling-primary-soft) !important;
            color: var(--bling-text-soft) !important;
            border: 1px solid rgba(79, 103, 165, 0.14) !important;
            font-size: 0.88rem !important;
            line-height: 1.32 !important;
            margin: 0.38rem 0 0.52rem 0 !important;
        }

        div[data-testid="stAlert"], .stAlert {
            border-radius: var(--bling-radius-lg) !important;
            box-shadow: none !important;
            padding-top: 0.54rem !important;
            padding-bottom: 0.54rem !important;
            margin-top: 0.28rem !important;
            margin-bottom: 0.28rem !important;
        }

        div[data-testid="stAlert"] p,
        div[data-testid="stAlert"] div {
            line-height: 1.28 !important;
            font-weight: 640 !important;
        }

        div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]),
        .stAlert:has([data-testid="stAlertContentSuccess"]) {
            background: var(--bling-success-bg) !important;
            border: 1px solid var(--bling-success-border) !important;
            color: var(--bling-success-text) !important;
        }

        div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]),
        .stAlert:has([data-testid="stAlertContentWarning"]) {
            background: var(--bling-warning-bg) !important;
            border: 1px solid var(--bling-warning-border) !important;
            color: var(--bling-warning-text) !important;
        }

        div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]),
        .stAlert:has([data-testid="stAlertContentError"]) {
            background: var(--bling-danger-bg) !important;
            border: 1px solid var(--bling-danger-border) !important;
            color: var(--bling-danger-text) !important;
        }

        div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]),
        .stAlert:has([data-testid="stAlertContentInfo"]) {
            background: var(--bling-info-bg) !important;
            border: 1px solid var(--bling-info-border) !important;
            color: var(--bling-info-text) !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFileUploader"] button,
        button[kind="secondary"] {
            min-height: 42px !important;
            border-radius: 15px !important;
            border: 1px solid var(--bling-border-strong) !important;
            background: #ffffff !important;
            color: var(--bling-text-soft) !important;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04) !important;
            font-weight: 760 !important;
            letter-spacing: 0.002em !important;
            white-space: normal !important;
            transition: background .16s ease, border-color .16s ease, box-shadow .16s ease, transform .16s ease !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        div[data-testid="stFileUploader"] button:hover,
        button[kind="secondary"]:hover {
            border-color: rgba(79, 103, 165, 0.42) !important;
            background: var(--bling-primary-soft) !important;
            box-shadow: 0 7px 18px rgba(79, 103, 165, 0.11) !important;
            transform: translateY(-1px) !important;
            color: var(--bling-primary-dark) !important;
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

        button[kind="primary"],
        .bling-primary-cta-anchor + div .stButton > button,
        div[data-testid="stVerticalBlock"]:has(.bling-primary-cta-anchor) .stButton > button {
            color: #ffffff !important;
            background: linear-gradient(135deg, var(--bling-primary), var(--bling-primary-dark)) !important;
            border-color: rgba(64, 88, 143, 0.42) !important;
            box-shadow: 0 10px 22px rgba(64, 88, 143, 0.22) !important;
            font-weight: 820 !important;
        }

        .stButton > button *,
        .stDownloadButton > button *,
        button[kind="primary"] *,
        button[kind="secondary"] * {
            color: inherit !important;
            font-weight: inherit !important;
        }

        div[data-testid="stFileUploader"] {
            width: min(100%, var(--bling-card-width)) !important;
            margin: 0 auto 0.72rem auto !important;
        }

        div[data-testid="stFileUploader"] section {
            border: 1px dashed rgba(79, 103, 165, 0.26) !important;
            border-radius: var(--bling-radius-xl) !important;
            background: rgba(255, 255, 255, 0.94) !important;
            box-shadow: var(--bling-shadow-soft) !important;
            padding: 0.85rem !important;
            min-height: 96px !important;
        }

        input,
        textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            border-radius: 14px !important;
            background: #ffffff !important;
            border-color: var(--bling-border-strong) !important;
            color: var(--bling-text) !important;
        }

        input::placeholder,
        textarea::placeholder { color: #94a3b8 !important; }

        div[data-testid="stDataFrame"] {
            border-radius: var(--bling-radius-lg) !important;
            overflow: hidden !important;
            border: 1px solid var(--bling-border) !important;
            background: #ffffff !important;
            box-shadow: var(--bling-shadow-soft) !important;
            max-height: 420px !important;
        }

        div[data-testid="stExpander"] details summary {
            min-height: 38px !important;
            padding-top: 0.38rem !important;
            padding-bottom: 0.38rem !important;
            font-weight: 780 !important;
            color: var(--bling-text-soft) !important;
        }

        .bling-wizard-progress-card {
            padding: 0.85rem 0.9rem !important;
        }

        .bling-wizard-progress-top {
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            gap: 0.65rem !important;
            margin-bottom: 0.55rem !important;
        }

        .bling-wizard-progress-title {
            font-size: 1rem !important;
            margin: 0 !important;
        }

        .bling-wizard-progress-percent {
            flex: 0 0 auto !important;
            min-width: 3rem !important;
            border-radius: 999px !important;
            background: var(--bling-primary-soft) !important;
            border: 1px solid rgba(79, 103, 165, 0.20) !important;
            color: var(--bling-primary-dark) !important;
            font-size: 0.78rem !important;
            font-weight: 850 !important;
            padding: 0.28rem 0.52rem !important;
            text-align: center !important;
        }

        .bling-wizard-progress-track {
            width: 100% !important;
            height: 0.42rem !important;
            border-radius: 999px !important;
            background: #e5edf8 !important;
            overflow: hidden !important;
        }

        .bling-wizard-progress-fill {
            height: 100% !important;
            border-radius: inherit !important;
            background: linear-gradient(90deg, var(--bling-primary), var(--bling-accent)) !important;
        }

        .bling-wizard-steps-line {
            display: flex !important;
            flex-wrap: wrap !important;
            gap: 0.34rem !important;
            margin-top: 0.62rem !important;
        }

        .bling-wizard-chip {
            display: inline-flex !important;
            align-items: center !important;
            gap: 0.28rem !important;
            border-radius: 999px !important;
            padding: 0.26rem 0.46rem !important;
            font-size: 0.72rem !important;
            font-weight: 760 !important;
            line-height: 1 !important;
            border: 1px solid var(--bling-border) !important;
            background: #ffffff !important;
            color: var(--bling-muted) !important;
            white-space: nowrap !important;
        }

        .bling-wizard-chip-active {
            border-color: rgba(79, 103, 165, 0.28) !important;
            background: var(--bling-primary-soft) !important;
            color: var(--bling-primary-dark) !important;
        }

        .bling-wizard-chip-done {
            border-color: var(--bling-success-border) !important;
            background: var(--bling-success-bg) !important;
            color: var(--bling-success-text) !important;
        }

        .bling-wizard-chip-dot {
            width: 0.36rem !important;
            height: 0.36rem !important;
            border-radius: 999px !important;
            display: inline-block !important;
            background: #cbd5e1 !important;
        }
        .bling-wizard-chip-dot-active { background: var(--bling-primary) !important; }
        .bling-wizard-chip-dot-done { background: #22c55e !important; }

        .bling-map-title {
            width: 100% !important;
            display: block !important;
            font-size: 0.86rem !important;
            line-height: 1.24 !important;
            font-weight: 820 !important;
            color: var(--bling-text) !important;
            margin: 0 0 0.35rem 0 !important;
            padding: 0 !important;
        }

        .bling-map-title-text {
            display: inline !important;
            overflow-wrap: normal !important;
            word-break: normal !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] label {
            display: none !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
            min-height: 36px !important;
            height: 36px !important;
            font-size: 0.85rem !important;
            box-shadow: none !important;
        }

        section[data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.96) !important;
            border-right: 1px solid rgba(203, 213, 225, 0.82) !important;
        }

        section[data-testid="stSidebar"] details {
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-lg) !important;
            background: rgba(255, 255, 255, 0.94) !important;
            box-shadow: var(--bling-shadow-soft) !important;
            overflow: hidden !important;
            margin-bottom: 0.52rem !important;
        }

        section[data-testid="stSidebar"] .stButton > button,
        section[data-testid="stSidebar"] .stDownloadButton > button {
            min-height: 38px !important;
            border-radius: 13px !important;
        }

        footer { visibility: hidden !important; }

        @media (max-width: 760px) {
            :root { --bling-content-width: 100vw; --bling-card-width: 100%; }

            .main .block-container,
            .block-container {
                width: 100% !important;
                max-width: 100vw !important;
                padding: 2.95rem 0.72rem 1rem 0.72rem !important;
            }

            div[data-testid="stVerticalBlock"] { gap: 0.48rem !important; }

            .bling-hero,
            .bling-flow-card,
            .bling-inline-card,
            div[data-testid="stFileUploader"] {
                width: 100% !important;
                margin: 0 0 0.52rem 0 !important;
            }

            .bling-hero,
            .bling-flow-card,
            .bling-inline-card {
                padding: 0.78rem 0.76rem !important;
                border-radius: 16px !important;
                box-shadow: 0 7px 16px rgba(15, 23, 42, 0.050) !important;
            }

            .bling-hero-kicker,
            .bling-flow-card-kicker,
            .bling-selected-flow-badge,
            .bling-home-pill,
            .bling-wizard-progress-kicker {
                font-size: 0.68rem !important;
                padding: 0.22rem 0.48rem !important;
                margin-bottom: 0.34rem !important;
            }

            .bling-hero-title,
            .bling-flow-card-title {
                font-size: 1.24rem !important;
                line-height: 1.10 !important;
                margin-bottom: 0.32rem !important;
            }

            .bling-hero-subtitle,
            .bling-flow-card-text,
            div[data-testid="stCaptionContainer"] {
                font-size: 0.86rem !important;
                line-height: 1.30 !important;
            }

            div[data-testid="stFileUploader"] section {
                min-height: 86px !important;
                padding: 0.72rem !important;
                border-radius: 16px !important;
            }

            .stButton > button,
            .stDownloadButton > button,
            div[data-testid="stFileUploader"] button,
            button[kind="primary"],
            button[kind="secondary"] {
                min-height: 40px !important;
                font-size: 0.91rem !important;
                border-radius: 14px !important;
            }

            .bling-wizard-progress-card { padding: 0.72rem !important; }
            .bling-wizard-progress-top { margin-bottom: 0.48rem !important; }
            .bling-wizard-progress-title { font-size: 0.94rem !important; }
            .bling-wizard-progress-percent { font-size: 0.72rem !important; min-width: 2.7rem !important; }
            .bling-wizard-steps-line { gap: 0.28rem !important; margin-top: 0.48rem !important; }
            .bling-wizard-chip { font-size: 0.68rem !important; padding: 0.24rem 0.40rem !important; }

            div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 0.72rem !important;
                border-radius: 14px !important;
                margin: 0.42rem 0 !important;
            }

            .bling-map-title { font-size: 0.82rem !important; }
            .bling-map-preview { font-size: 0.80rem !important; }
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
