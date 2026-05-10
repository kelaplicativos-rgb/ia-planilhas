from __future__ import annotations

import streamlit as st


def inject_sidebar_skin() -> None:
    """Aplica a skin visual padrão da sidebar em todos os painéis laterais."""
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #07111f 0%, #0b1628 52%, #0f1b2d 100%) !important;
            border-right: 1px solid rgba(148, 163, 184, 0.18) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding: 1rem 0.85rem 1.25rem 0.85rem !important;
        }

        section[data-testid="stSidebar"] * {
            color: #e5eefb !important;
        }

        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        section[data-testid="stSidebar"] p {
            color: rgba(226, 232, 240, 0.78) !important;
        }

        section[data-testid="stSidebar"] details {
            border: 1px solid rgba(148, 163, 184, 0.22) !important;
            border-radius: 18px !important;
            background: rgba(15, 23, 42, 0.72) !important;
            box-shadow: 0 14px 36px rgba(0, 0, 0, 0.24) !important;
            margin-bottom: 0.85rem !important;
            overflow: hidden !important;
        }

        section[data-testid="stSidebar"] details > summary {
            font-weight: 800 !important;
            letter-spacing: -0.01em !important;
            padding: 0.88rem 0.95rem !important;
            border-radius: 18px !important;
            background: rgba(15, 23, 42, 0.42) !important;
        }

        section[data-testid="stSidebar"] details[open] > summary {
            border-bottom: 1px solid rgba(148, 163, 184, 0.14) !important;
            border-radius: 18px 18px 0 0 !important;
        }

        section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(148, 163, 184, 0.22) !important;
            border-radius: 16px !important;
            background: rgba(255, 255, 255, 0.045) !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
        }

        section[data-testid="stSidebar"] div[data-testid="stForm"] {
            border: 1px solid rgba(148, 163, 184, 0.22) !important;
            border-radius: 16px !important;
            background: rgba(255, 255, 255, 0.045) !important;
            padding: 0.8rem !important;
        }

        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea,
        section[data-testid="stSidebar"] [data-baseweb="input"] {
            background: rgba(2, 6, 23, 0.72) !important;
            border-color: rgba(148, 163, 184, 0.24) !important;
            border-radius: 12px !important;
            color: #f8fafc !important;
        }

        section[data-testid="stSidebar"] .stButton > button,
        section[data-testid="stSidebar"] .stDownloadButton > button,
        section[data-testid="stSidebar"] button[kind="secondary"],
        section[data-testid="stSidebar"] button[kind="primary"] {
            border-radius: 13px !important;
            border: 1px solid rgba(96, 165, 250, 0.34) !important;
            background: rgba(37, 99, 235, 0.18) !important;
            color: #eff6ff !important;
            font-weight: 800 !important;
            min-height: 2.42rem !important;
            transition: all 0.16s ease !important;
        }

        section[data-testid="stSidebar"] .stButton > button:hover,
        section[data-testid="stSidebar"] .stDownloadButton > button:hover {
            border-color: rgba(96, 165, 250, 0.76) !important;
            background: rgba(37, 99, 235, 0.34) !important;
            transform: translateY(-1px) !important;
        }

        section[data-testid="stSidebar"] [data-testid="stRadio"] label,
        section[data-testid="stSidebar"] [data-testid="stToggle"] label {
            color: #e5eefb !important;
            font-weight: 700 !important;
        }

        section[data-testid="stSidebar"] hr {
            border-color: rgba(148, 163, 184, 0.16) !important;
            margin: 0.75rem 0 !important;
        }

        .bling-sidebar-title {
            font-size: 0.86rem;
            line-height: 1.2;
            font-weight: 900;
            letter-spacing: -0.015em;
            color: #f8fafc !important;
            margin: 0 0 0.18rem 0;
        }

        .bling-sidebar-subtitle {
            font-size: 0.74rem;
            line-height: 1.35;
            color: rgba(226, 232, 240, 0.74) !important;
            margin: 0 0 0.55rem 0;
        }

        .bling-sidebar-pill-row {
            display: flex;
            gap: 0.35rem;
            flex-wrap: wrap;
            margin: 0.3rem 0 0.55rem 0;
        }

        .bling-sidebar-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.16rem 0.48rem;
            border: 1px solid rgba(148, 163, 184, 0.22);
            background: rgba(15, 23, 42, 0.72);
            color: #dbeafe !important;
            font-size: 0.68rem;
            font-weight: 800;
            white-space: nowrap;
        }

        .bling-sidebar-pill.on {
            border-color: rgba(34, 197, 94, 0.45);
            background: rgba(22, 163, 74, 0.18);
            color: #dcfce7 !important;
        }

        .bling-sidebar-pill.off {
            border-color: rgba(251, 146, 60, 0.44);
            background: rgba(249, 115, 22, 0.14);
            color: #ffedd5 !important;
        }

        .bling-sidebar-mini-label {
            font-size: 0.72rem;
            font-weight: 900;
            color: #bfdbfe !important;
            margin-bottom: 0.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_header(title: str, subtitle: str = '') -> None:
    subtitle_html = f'<p class="bling-sidebar-subtitle">{subtitle}</p>' if subtitle else ''
    st.markdown(
        f'<div class="bling-sidebar-title">{title}</div>{subtitle_html}',
        unsafe_allow_html=True,
    )


def sidebar_pills(*items: tuple[str, bool]) -> None:
    if not items:
        return
    pills = []
    for label, active in items:
        state = 'on' if bool(active) else 'off'
        pills.append(f'<span class="bling-sidebar-pill {state}">{label}</span>')
    st.markdown('<div class="bling-sidebar-pill-row">' + ''.join(pills) + '</div>', unsafe_allow_html=True)


def sidebar_mini_label(label: str) -> None:
    st.markdown(f'<div class="bling-sidebar-mini-label">{label}</div>', unsafe_allow_html=True)
