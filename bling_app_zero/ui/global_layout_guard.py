from __future__ import annotations

import streamlit as st


def inject_global_layout_guard() -> None:
    """Protecao visual global para evitar topo cortado em todos os fluxos.

    Esta camada fica por ultimo no CSS da Home e vale para site, cadastro,
    estoque e telas intermediarias, porque todos passam por render_home().
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
        }

        .main .block-container,
        .block-container {
            max-width: 1080px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-top: 4.25rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            overflow-x: hidden !important;
            box-sizing: border-box !important;
        }

        .bling-hero {
            width: min(100%, 860px) !important;
            max-width: calc(100vw - 2rem) !important;
            margin: 1.10rem auto 1.00rem auto !important;
            text-align: center !important;
            box-sizing: border-box !important;
            overflow: hidden !important;
            transform: none !important;
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

        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                max-width: 100vw !important;
                padding-top: 3.55rem !important;
                padding-left: 0.70rem !important;
                padding-right: 0.70rem !important;
            }

            .bling-hero {
                width: 100% !important;
                max-width: 100% !important;
                margin: 0.85rem auto 0.75rem auto !important;
            }

            .bling-home-card {
                width: 100% !important;
                max-width: 100% !important;
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
