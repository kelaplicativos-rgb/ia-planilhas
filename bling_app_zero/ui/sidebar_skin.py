from __future__ import annotations

import streamlit as st


def _safe_html(value: str) -> str:
    return str(value or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def inject_sidebar_skin() -> None:
    """Integra a sidebar ao mesmo tema visual usado no sistema central."""
    st.markdown(
        """
        <style id="bling-sidebar-theme-bridge">
        section[data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 18% 0%, rgba(56, 189, 248, 0.12), transparent 16rem),
                linear-gradient(180deg, rgba(255,255,255,0.98) 0%, var(--bling-bg) 100%) !important;
            border-right: 1px solid rgba(191, 219, 254, 0.72) !important;
            color: var(--bling-text) !important;
            overflow-x: hidden !important;
        }

        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] * {
            box-sizing: border-box !important;
            max-width: 100% !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding: 0.95rem 0.72rem 1.2rem 0.72rem !important;
            overflow-x: hidden !important;
        }

        section[data-testid="stSidebar"] * {
            color: var(--bling-text) !important;
        }

        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        section[data-testid="stSidebar"] p {
            color: var(--bling-muted) !important;
            font-size: 0.72rem !important;
            line-height: 1.32 !important;
        }

        section[data-testid="stSidebar"] details,
        section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"],
        section[data-testid="stSidebar"] div[data-testid="stForm"] {
            border: 1px solid var(--bling-border) !important;
            border-radius: var(--bling-radius-lg) !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,247,255,0.94)) !important;
            box-shadow: var(--bling-shadow-soft) !important;
            overflow: hidden !important;
        }

        section[data-testid="stSidebar"] details {
            margin-bottom: 0.75rem !important;
        }

        section[data-testid="stSidebar"] details > summary {
            font-weight: 820 !important;
            font-size: 0.86rem !important;
            line-height: 1.18 !important;
            letter-spacing: -0.01em !important;
            padding: 0.78rem 0.76rem !important;
            color: var(--bling-text) !important;
            background: rgba(239, 246, 255, 0.72) !important;
            white-space: normal !important;
        }

        section[data-testid="stSidebar"] details[open] > summary {
            border-bottom: 1px solid var(--bling-border) !important;
        }

        section[data-testid="stSidebar"] details[open] > div {
            padding: 0.68rem 0.74rem 0.82rem 0.74rem !important;
            overflow-x: hidden !important;
        }

        section[data-testid="stSidebar"] details[open] > div > div,
        section[data-testid="stSidebar"] details[open] [data-testid="stVerticalBlock"] {
            gap: 0.42rem !important;
            overflow-x: hidden !important;
        }

        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea,
        section[data-testid="stSidebar"] [data-baseweb="input"] {
            background: #ffffff !important;
            border-color: rgba(37, 99, 235, 0.16) !important;
            border-radius: var(--bling-radius-md) !important;
            color: var(--bling-text) !important;
            font-size: 0.82rem !important;
        }

        section[data-testid="stSidebar"] .stButton > button,
        section[data-testid="stSidebar"] .stDownloadButton > button,
        section[data-testid="stSidebar"] button[kind="secondary"] {
            border-radius: var(--bling-radius-md) !important;
            border: 1px solid rgba(37, 99, 235, 0.18) !important;
            background: #ffffff !important;
            color: var(--bling-text) !important;
            box-shadow: 0 6px 16px rgba(15, 23, 42, 0.045) !important;
            font-weight: 760 !important;
            min-height: 2.28rem !important;
            padding: 0.35rem 0.52rem !important;
            transition: all 0.16s ease !important;
            white-space: normal !important;
            line-height: 1.18 !important;
            font-size: 0.80rem !important;
        }

        section[data-testid="stSidebar"] button[kind="primary"] {
            color: #ffffff !important;
            background: linear-gradient(135deg, var(--bling-primary), var(--bling-primary-dark)) !important;
            border-color: rgba(37, 99, 235, 0.34) !important;
            box-shadow: 0 12px 28px rgba(37, 99, 235, 0.22) !important;
        }

        section[data-testid="stSidebar"] .stButton > button:hover,
        section[data-testid="stSidebar"] .stDownloadButton > button:hover {
            border-color: rgba(37, 99, 235, 0.34) !important;
            background: var(--bling-surface-soft) !important;
            box-shadow: 0 10px 22px rgba(37, 99, 235, 0.10) !important;
            transform: translateY(-1px) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stRadio"] {
            padding: 0.12rem 0 !important;
        }

        section[data-testid="stSidebar"] [data-testid="stRadio"] > div {
            gap: 0.14rem !important;
        }

        section[data-testid="stSidebar"] [data-testid="stRadio"] label,
        section[data-testid="stSidebar"] [data-testid="stToggle"] label {
            color: var(--bling-text) !important;
            font-weight: 720 !important;
            font-size: 0.76rem !important;
            line-height: 1.22 !important;
            white-space: normal !important;
        }

        section[data-testid="stSidebar"] [data-testid="stRadio"] label > div,
        section[data-testid="stSidebar"] [data-testid="stToggle"] label > div {
            min-width: 0 !important;
        }

        section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
            gap: 0.35rem !important;
            overflow-x: hidden !important;
        }

        section[data-testid="stSidebar"] hr {
            border-color: rgba(37, 99, 235, 0.12) !important;
            margin: 0.55rem 0 !important;
        }

        .bling-sidebar-title {
            font-size: 0.78rem;
            line-height: 1.18;
            font-weight: 880;
            letter-spacing: -0.01em;
            color: var(--bling-text) !important;
            margin: 0 0 0.14rem 0;
            max-width: 100%;
            overflow-wrap: normal;
            word-break: normal;
        }

        .bling-sidebar-subtitle {
            font-size: 0.68rem;
            line-height: 1.30;
            color: var(--bling-muted) !important;
            margin: 0 0 0.42rem 0;
            max-width: 100%;
            overflow-wrap: normal;
            word-break: normal;
        }

        .bling-sidebar-pill-row {
            display: flex;
            gap: 0.26rem;
            flex-wrap: wrap;
            margin: 0.22rem 0 0.42rem 0;
            max-width: 100%;
            overflow-x: hidden;
        }

        .bling-sidebar-pill {
            display: inline-flex;
            align-items: center;
            max-width: 100%;
            border-radius: 999px;
            padding: 0.14rem 0.40rem;
            border: 1px solid rgba(37, 99, 235, 0.14);
            background: rgba(37, 99, 235, 0.10);
            color: var(--bling-primary-dark) !important;
            font-size: 0.61rem;
            line-height: 1.15;
            font-weight: 800;
            white-space: normal;
            overflow-wrap: normal;
            word-break: normal;
        }

        .bling-sidebar-pill.on {
            border-color: rgba(22, 101, 52, 0.18);
            background: var(--bling-success-bg);
            color: var(--bling-success-text) !important;
        }

        .bling-sidebar-pill.off {
            border-color: rgba(202, 138, 4, 0.22);
            background: rgba(254, 252, 232, 0.94);
            color: var(--bling-warning) !important;
        }

        .bling-sidebar-mini-label {
            font-size: 0.66rem;
            line-height: 1.18;
            font-weight: 860;
            color: var(--bling-primary-dark) !important;
            margin-bottom: 0.18rem;
            max-width: 100%;
            overflow-wrap: normal;
            word-break: normal;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_header(title: str, subtitle: str = '') -> None:
    safe_title = _safe_html(title)
    safe_subtitle = _safe_html(subtitle)
    subtitle_html = f'<p class="bling-sidebar-subtitle">{safe_subtitle}</p>' if safe_subtitle else ''
    st.markdown(f'<div class="bling-sidebar-title">{safe_title}</div>{subtitle_html}', unsafe_allow_html=True)


def sidebar_pills(*items: tuple[str, bool]) -> None:
    if not items:
        return
    pills = []
    for label, active in items:
        state = 'on' if bool(active) else 'off'
        safe_label = _safe_html(label)
        pills.append(f'<span class="bling-sidebar-pill {state}">{safe_label}</span>')
    st.markdown('<div class="bling-sidebar-pill-row">' + ''.join(pills) + '</div>', unsafe_allow_html=True)


def sidebar_mini_label(label: str) -> None:
    safe_label = _safe_html(label)
    st.markdown(f'<div class="bling-sidebar-mini-label">{safe_label}</div>', unsafe_allow_html=True)
