from __future__ import annotations

import streamlit as st


def inject_sidebar_tools_theme() -> None:
    """Tema oficial da barra lateral técnica.

    Centraliza o visual da sidebar e dos campos de regras. Este arquivo deve ser
    o único responsável pela borda/fundo padrão das ferramentas laterais.
    """
    st.markdown(
        """
        <style id="bling-sidebar-tools-theme">
        section[data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 18% 0%, rgba(56, 189, 248, 0.10), transparent 14rem),
                linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 251, 255, 0.96)) !important;
            border-right: 1px solid rgba(191, 219, 254, 0.72) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding-top: 0.75rem !important;
        }

        .bling-sidebar-hero {
            width: 100% !important;
            margin: 0 0 0.85rem 0 !important;
            padding: 0.95rem 0.88rem !important;
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-lg) !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,247,255,0.96)) !important;
            box-shadow: var(--bling-shadow-soft) !important;
            position: relative !important;
            overflow: hidden !important;
        }

        .bling-sidebar-hero::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--bling-primary), var(--bling-accent));
        }

        .bling-sidebar-kicker {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 0 0.5rem 0 !important;
            padding: 0.26rem 0.58rem !important;
            border-radius: 999px !important;
            background: rgba(37, 99, 235, 0.10) !important;
            border: 1px solid rgba(37, 99, 235, 0.12) !important;
            color: var(--bling-primary-dark) !important;
            font-size: 0.72rem !important;
            font-weight: 820 !important;
            line-height: 1.1 !important;
        }

        .bling-sidebar-title {
            color: var(--bling-text) !important;
            font-size: 1.05rem !important;
            font-weight: 900 !important;
            letter-spacing: -0.02em !important;
            line-height: 1.12 !important;
            margin: 0 0 0.35rem 0 !important;
        }

        .bling-sidebar-text {
            color: var(--bling-muted) !important;
            font-size: 0.84rem !important;
            line-height: 1.34 !important;
            margin: 0 !important;
        }

        section[data-testid="stSidebar"] details {
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-lg) !important;
            background: rgba(255, 255, 255, 0.94) !important;
            box-shadow: var(--bling-shadow-soft) !important;
            overflow: hidden !important;
            margin-bottom: 0.78rem !important;
        }

        section[data-testid="stSidebar"] summary {
            color: var(--bling-text) !important;
            font-weight: 850 !important;
            letter-spacing: -0.01em !important;
        }

        section[data-testid="stSidebar"] details div[data-testid="stExpanderDetails"] {
            border-top: 1px solid rgba(37, 99, 235, 0.08) !important;
            background: rgba(255, 255, 255, 0.72) !important;
        }

        section[data-testid="stSidebar"] .stButton > button,
        section[data-testid="stSidebar"] .stDownloadButton > button {
            min-height: 40px !important;
            border-radius: 13px !important;
            box-shadow: 0 5px 14px rgba(15, 23, 42, 0.04) !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stDataFrame"] {
            border-radius: 14px !important;
            box-shadow: none !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(input[id*="rule_value_"]) {
            padding: 0.72rem 0.72rem 0.42rem 0.72rem !important;
            margin: 0.55rem 0 0.78rem 0 !important;
            border: 1px solid rgba(37, 99, 235, 0.20) !important;
            border-left: 4px solid rgba(37, 99, 235, 0.72) !important;
            border-radius: 16px !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,247,255,0.96)) !important;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.045) !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(input[id*="rule_value_"]) input {
            min-height: 39px !important;
            border-radius: 12px !important;
            border: 1px solid rgba(37, 99, 235, 0.26) !important;
            background: #ffffff !important;
            color: var(--bling-text) !important;
            font-size: 0.93rem !important;
            font-weight: 650 !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"]:has(input[id*="rule_value_"]) div[data-testid="stToggle"] {
            margin-top: -0.12rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


__all__ = ['inject_sidebar_tools_theme']
