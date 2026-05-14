from __future__ import annotations

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/human_compact_mode.py'


def inject_human_compact_mode() -> None:
    """Camada global #all para reduzir poluição visual.

    O objetivo é deixar o sistema mais direto para operação humana:
    menos leitura obrigatória, menos espaços mortos, cards mais compactos e botões mais claros.
    """
    st.markdown(
        """
        <style id="bling-human-compact-mode-all">
        :root {
            --bling-compact-content-width: 820px;
        }

        .main .block-container,
        .block-container {
            width: min(100%, var(--bling-compact-content-width)) !important;
            max-width: var(--bling-compact-content-width) !important;
            padding-top: 3.35rem !important;
            padding-bottom: 1.1rem !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.52rem !important;
        }

        .bling-hero,
        .bling-flow-card,
        .bling-inline-card,
        div[data-testid="stForm"],
        div[data-testid="stExpander"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px !important;
            box-shadow: 0 6px 14px rgba(15, 23, 42, 0.045) !important;
        }

        .bling-hero,
        .bling-flow-card,
        .bling-inline-card {
            width: min(100%, 680px) !important;
            padding: 0.88rem 0.92rem !important;
            margin-bottom: 0.62rem !important;
        }

        .bling-hero-kicker,
        .bling-flow-card-kicker,
        .bling-selected-flow-badge,
        .bling-home-pill {
            font-size: 0.70rem !important;
            padding: 0.24rem 0.52rem !important;
            margin-bottom: 0.38rem !important;
        }

        .bling-hero-title,
        .bling-flow-card-title,
        .bling-step-title,
        h1, h2, h3, h4, h5 {
            letter-spacing: -0.026em !important;
            line-height: 1.08 !important;
            margin-bottom: 0.28rem !important;
        }

        h1 { font-size: clamp(1.58rem, 4.4vw, 2.18rem) !important; }
        h2 { font-size: clamp(1.36rem, 3.8vw, 1.86rem) !important; }
        h3 { font-size: clamp(1.12rem, 3.3vw, 1.48rem) !important; }
        h4 { font-size: 1.05rem !important; }

        .bling-hero-subtitle,
        .bling-flow-card-text,
        .bling-muted,
        .bling-upload-caption,
        div[data-testid="stCaptionContainer"],
        div[data-testid="stMarkdownContainer"] p {
            line-height: 1.32 !important;
        }

        div[data-testid="stCaptionContainer"] {
            font-size: 0.86rem !important;
        }

        .element-container:has(.stMarkdown) {
            margin-bottom: 0.04rem !important;
        }

        hr,
        .stDivider,
        div[data-testid="stDecoration"] {
            margin-top: 0.35rem !important;
            margin-bottom: 0.35rem !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFileUploader"] button,
        button[kind="primary"],
        button[kind="secondary"] {
            min-height: 42px !important;
            border-radius: 15px !important;
            font-size: 0.95rem !important;
            padding-top: 0.48rem !important;
            padding-bottom: 0.48rem !important;
        }

        div[data-testid="stFileUploader"] {
            margin-bottom: 0.55rem !important;
        }

        div[data-testid="stFileUploader"] section {
            min-height: 88px !important;
            padding: 0.72rem !important;
            border-radius: 16px !important;
        }

        div[data-testid="stAlert"] {
            border-radius: 14px !important;
            padding-top: 0.52rem !important;
            padding-bottom: 0.52rem !important;
            margin-top: 0.32rem !important;
            margin-bottom: 0.32rem !important;
        }

        div[data-testid="stAlert"] p,
        div[data-testid="stAlert"] div {
            line-height: 1.30 !important;
        }

        div[data-testid="stExpander"] details summary {
            min-height: 40px !important;
            padding-top: 0.4rem !important;
            padding-bottom: 0.4rem !important;
        }

        div[data-testid="stDataFrame"] {
            max-height: 380px !important;
        }

        input,
        textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            border-radius: 14px !important;
        }

        /* Reduz textos auxiliares muito longos sem esconder função principal. */
        div[data-testid="stMarkdownContainer"] p:only-child {
            max-width: 66ch !important;
        }

        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                padding: 2.85rem 0.72rem 0.9rem 0.72rem !important;
            }

            .bling-hero,
            .bling-flow-card,
            .bling-inline-card {
                padding: 0.76rem 0.76rem !important;
                margin-bottom: 0.48rem !important;
                border-radius: 16px !important;
            }

            .bling-hero-title,
            .bling-flow-card-title {
                font-size: 1.30rem !important;
            }

            h1 { font-size: 1.58rem !important; }
            h2 { font-size: 1.34rem !important; }
            h3 { font-size: 1.16rem !important; }

            .stButton > button,
            .stDownloadButton > button,
            div[data-testid="stFileUploader"] button,
            button[kind="primary"],
            button[kind="secondary"] {
                min-height: 41px !important;
                font-size: 0.93rem !important;
                border-radius: 14px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


__all__ = ['inject_human_compact_mode']
