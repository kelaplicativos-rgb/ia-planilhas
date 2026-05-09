from __future__ import annotations

import streamlit as st


def inject_global_layout_guard() -> None:
    """Proteção visual global do app.

    Mantém o mesmo padrão visual do print aprovado em todas as telas:
    topo centralizado, conteúdo na mesma largura, respiro superior,
    sem corte lateral e comportamento seguro em desktop/mobile.
    """
    st.markdown(
        """
        <style>
        html,
        body,
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"] {
            max-width: 100vw !important;
            overflow-x: hidden !important;
            background: #ffffff !important;
        }

        .main .block-container,
        .block-container {
            max-width: 1040px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-top: 4.15rem !important;
            padding-left: 0.85rem !important;
            padding-right: 0.85rem !important;
            padding-bottom: 2.3rem !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }

        .bling-hero {
            width: min(100%, 860px) !important;
            max-width: calc(100vw - 2rem) !important;
            margin: 1.05rem auto 0.90rem auto !important;
            text-align: center !important;
            box-sizing: border-box !important;
            overflow: hidden !important;
            transform: none !important;
            border: 1px solid rgba(49, 51, 63, 0.10) !important;
            border-radius: 14px !important;
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(249,250,252,0.96)) !important;
            box-shadow: 0 10px 32px rgba(15, 23, 42, 0.035) !important;
        }

        .bling-hero-title,
        .bling-hero-subtitle {
            text-align: center !important;
            max-width: 100% !important;
            overflow-wrap: anywhere !important;
            word-break: normal !important;
        }

        .bling-home-center {
            width: 100% !important;
            display: flex !important;
            justify-content: center !important;
            align-items: flex-start !important;
            box-sizing: border-box !important;
            overflow: visible !important;
        }

        .bling-home-card {
            width: min(100%, 760px) !important;
            max-width: calc(100vw - 2rem) !important;
            margin-left: auto !important;
            margin-right: auto !important;
            box-sizing: border-box !important;
            overflow: hidden !important;
        }

        div[data-testid="stVerticalBlock"],
        div[data-testid="stHorizontalBlock"],
        div[data-testid="stElementContainer"],
        div[data-testid="column"] {
            max-width: 100% !important;
            box-sizing: border-box !important;
            overflow-x: hidden !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.58rem !important;
        }

        div[data-testid="stHorizontalBlock"] {
            width: 100% !important;
        }

        div[data-testid="column"] {
            min-width: 0 !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 13px !important;
            white-space: normal !important;
            max-width: 100% !important;
        }

        div[data-testid="stFileUploader"],
        div[data-testid="stFileUploader"] section,
        div[data-testid="stFileUploader"] section > div {
            max-width: 100% !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }

        div[data-baseweb="select"],
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"],
        div[data-baseweb="textarea"] {
            max-width: 100% !important;
            box-sizing: border-box !important;
            overflow-x: hidden !important;
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stDataFrame"] > div,
        iframe {
            max-width: 100% !important;
            overflow-x: auto !important;
            box-sizing: border-box !important;
        }

        section[data-testid="stSidebar"] {
            z-index: 999999 !important;
        }

        @media (min-width: 761px) {
            .main .block-container,
            .block-container {
                width: min(100%, 1040px) !important;
            }
        }

        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                max-width: 100vw !important;
                width: 100% !important;
                padding-top: 3.55rem !important;
                padding-left: 0.70rem !important;
                padding-right: 0.70rem !important;
                padding-bottom: 1.4rem !important;
            }

            .bling-hero {
                width: 100% !important;
                max-width: 100% !important;
                margin: 0.85rem auto 0.75rem auto !important;
                border-radius: 14px !important;
            }

            .bling-home-card {
                width: 100% !important;
                max-width: 100% !important;
            }

            div[data-testid="stHorizontalBlock"] {
                gap: 0.42rem !important;
            }
        }

        @media (max-width: 390px) {
            .main .block-container,
            .block-container {
                padding-top: 3.25rem !important;
                padding-left: 0.55rem !important;
                padding-right: 0.55rem !important;
            }

            .bling-hero {
                margin-top: 0.72rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
