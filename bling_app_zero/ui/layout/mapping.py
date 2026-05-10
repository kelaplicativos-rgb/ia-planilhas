from __future__ import annotations

import html

import streamlit as st


def inject_mapping_css() -> None:
    """Ajustes especificos do mapeamento herdando o tema global."""
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
            overflow: visible !important;
            border-radius: var(--bling-radius-md, 14px) !important;
            border: 1px solid var(--bling-border, rgba(37, 99, 235, 0.14)) !important;
            background: var(--bling-surface, #ffffff) !important;
            padding: 16px 12px 13px 12px !important;
            margin: 0.55rem 0 0.78rem 0 !important;
            box-shadow: var(--bling-shadow-soft, 0 8px 22px rgba(15, 23, 42, 0.045)) !important;
            min-height: 100px !important;
            height: auto !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
            gap: 0.34rem !important;
            overflow: visible !important;
        }

        .bling-map-title {
            width: 100%;
            display: block;
            position: relative;
            z-index: 2;
            font-size: 0.85rem;
            line-height: 1.26;
            font-weight: 820;
            color: var(--bling-text, #0f172a) !important;
            margin: 0 0 6px 0 !important;
            padding: 0 !important;
            text-align: left;
            overflow-wrap: normal;
            word-break: normal;
            hyphens: none;
        }

        .bling-map-title-red { color: var(--bling-danger, #dc2626) !important; }
        .bling-map-title-yellow { color: var(--bling-warning, #ca8a04) !important; }
        .bling-map-title-green { color: var(--bling-success-text, #166534) !important; }

        .bling-map-title-text {
            display: inline;
            min-width: 0;
            overflow-wrap: normal;
            word-break: normal;
        }

        .bling-map-help {
            display: none !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] {
            display: block !important;
            position: relative !important;
            z-index: 1;
            width: 100% !important;
            max-width: 100% !important;
            overflow: visible !important;
            margin: 0 0 5px 0 !important;
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
            clear: both !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] label {
            display: none !important;
            height: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] {
            display: block !important;
            width: 100% !important;
            max-width: 100% !important;
            margin: 0 !important;
            position: static !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
            min-height: 36px !important;
            height: 36px !important;
            background: rgba(239, 246, 255, 0.82) !important;
            border: 1px solid rgba(37, 99, 235, 0.16) !important;
            border-radius: 12px !important;
            box-shadow: none !important;
            max-width: 100% !important;
            overflow: hidden !important;
            font-size: 0.85rem !important;
            display: flex !important;
            align-items: center !important;
        }

        div[data-testid="stVerticalBlock"] > div:has(.bling-map-title-red) + div div[data-baseweb="select"] > div {
            background: rgba(254, 242, 242, 0.78) !important;
            border-color: rgba(220, 38, 38, 0.22) !important;
        }

        div[data-testid="stVerticalBlock"] > div:has(.bling-map-title-yellow) + div div[data-baseweb="select"] > div {
            background: rgba(254, 252, 232, 0.82) !important;
            border-color: rgba(202, 138, 4, 0.22) !important;
        }

        div[data-testid="stVerticalBlock"] > div:has(.bling-map-title-green) + div div[data-baseweb="select"] > div {
            background: rgba(240, 253, 244, 0.82) !important;
            border-color: rgba(22, 163, 74, 0.22) !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] span {
            max-width: 100% !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            line-height: 1.20 !important;
            font-size: 0.85rem !important;
        }

        .bling-map-preview {
            display: block;
            position: relative;
            z-index: 1;
            width: 100%;
            font-size: 0.82rem;
            line-height: 1.28;
            color: rgba(30, 64, 175, 0.82) !important;
            font-weight: 760;
            padding: 0 !important;
            margin: -1px 0 0 0 !important;
            border-radius: 0;
            background: transparent !important;
            border: 0;
            text-align: left;
            overflow-wrap: break-word;
            word-break: normal;
            hyphens: none;
        }

        @media (max-width: 760px) {
            div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 15px 10px 12px 10px !important;
                margin: 0.5rem 0 0.72rem 0 !important;
                border-radius: 14px !important;
                min-height: 98px !important;
                height: auto !important;
                overflow: visible !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
                gap: 0.32rem !important;
                overflow: visible !important;
            }

            .bling-map-title {
                position: relative;
                z-index: 2;
                font-size: 0.83rem;
                line-height: 1.24;
                margin: 0 0 6px 0 !important;
                padding: 0 !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] {
                position: relative !important;
                z-index: 1;
                margin: 0 0 4px 0 !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
                min-height: 35px !important;
                height: 35px !important;
                border-radius: 12px !important;
                font-size: 0.83rem !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] span {
                font-size: 0.83rem !important;
                line-height: 1.18 !important;
            }

            .bling-map-preview {
                position: relative;
                z-index: 1;
                font-size: 0.82rem;
                line-height: 1.26;
                color: rgba(30, 64, 175, 0.82) !important;
                background: transparent !important;
                padding: 0 !important;
                margin: -1px 0 0 0 !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_mapping_title(target_label: str) -> None:
    raw = str(target_label or '')
    safe = html.escape(raw)
    status_class = ''
    if raw.startswith('🔴'):
        status_class = ' bling-map-title-red'
    elif raw.startswith('🟡'):
        status_class = ' bling-map-title-yellow'
    elif raw.startswith('🟢'):
        status_class = ' bling-map-title-green'
    st.markdown(
        f'<div class="bling-map-title{status_class}"><span class="bling-map-title-text">{safe}</span><span class="bling-map-help">?</span></div>',
        unsafe_allow_html=True,
    )


def render_mapping_preview(text: str) -> None:
    safe = html.escape(str(text or '').strip())
    if not safe:
        return
    st.markdown(f'<div class="bling-map-preview">{safe}</div>', unsafe_allow_html=True)


__all__ = ['inject_mapping_css', 'render_mapping_title', 'render_mapping_preview']
