from __future__ import annotations

import streamlit as st


def inject_sidebar_tools_theme() -> None:
    """Complemento visual da sidebar usando as variáveis do tema global.

    Este arquivo não cria um tema paralelo. Ele apenas aplica acabamento nos
    módulos técnicos que ficam dentro da sidebar, reaproveitando as variáveis
    definidas em bling_app_zero.ui.layout.theme.
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

        .bling-rule-pro-card {
            margin: 0.48rem 0 0.72rem 0 !important;
            padding: 0.72rem 0.72rem 0.22rem 0.72rem !important;
            border-radius: 16px !important;
            border: 1px solid rgba(37, 99, 235, 0.12) !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(248,251,255,0.95)) !important;
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.035) !important;
        }

        .bling-rule-pro-head {
            display: flex !important;
            align-items: flex-start !important;
            justify-content: space-between !important;
            gap: 0.65rem !important;
            margin-bottom: 0.52rem !important;
        }

        .bling-rule-pro-label {
            color: var(--bling-muted) !important;
            font-size: 0.68rem !important;
            font-weight: 760 !important;
            line-height: 1.1 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.04em !important;
            margin-bottom: 0.18rem !important;
        }

        .bling-rule-pro-title {
            color: var(--bling-text) !important;
            font-size: 0.98rem !important;
            font-weight: 880 !important;
            line-height: 1.15 !important;
            letter-spacing: -0.01em !important;
        }

        .bling-rule-pro-badge {
            flex: 0 0 auto !important;
            padding: 0.18rem 0.48rem !important;
            border-radius: 999px !important;
            font-size: 0.68rem !important;
            font-weight: 820 !important;
            line-height: 1.15 !important;
            border: 1px solid rgba(37, 99, 235, 0.14) !important;
            background: rgba(37, 99, 235, 0.08) !important;
            color: var(--bling-primary-dark) !important;
        }

        .bling-rule-pro-badge.is-muted {
            border-color: rgba(100, 116, 139, 0.18) !important;
            background: rgba(100, 116, 139, 0.08) !important;
            color: var(--bling-muted) !important;
        }

        .bling-rule-pro-card label,
        .bling-rule-pro-card div[data-testid="stWidgetLabel"] p {
            font-size: 0.76rem !important;
            color: var(--bling-muted) !important;
            font-weight: 720 !important;
            line-height: 1.16 !important;
        }

        .bling-rule-pro-card div[data-testid="stTextInput"] {
            margin-top: -0.28rem !important;
        }

        .bling-rule-pro-card input {
            min-height: 38px !important;
            font-size: 0.92rem !important;
            font-weight: 650 !important;
            color: var(--bling-text) !important;
            border-radius: 12px !important;
            border: 1px solid rgba(37, 99, 235, 0.18) !important;
            background: #ffffff !important;
        }

        .bling-rule-pro-card div[data-testid="stToggle"] {
            margin: -0.15rem 0 0.18rem 0 !important;
        }

        .bling-rule-pro-card div[data-testid="stToggle"] label {
            gap: 0.42rem !important;
        }

        @media (max-width: 760px) {
            .bling-rule-pro-card {
                padding: 0.66rem 0.66rem 0.2rem 0.66rem !important;
                border-radius: 15px !important;
                margin-bottom: 0.62rem !important;
            }

            .bling-rule-pro-title {
                font-size: 0.94rem !important;
            }

            .bling-rule-pro-badge {
                font-size: 0.64rem !important;
                padding: 0.16rem 0.42rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


__all__ = ['inject_sidebar_tools_theme']
