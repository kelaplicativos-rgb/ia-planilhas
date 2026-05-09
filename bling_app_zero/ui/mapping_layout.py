from __future__ import annotations

import html

import streamlit as st


def inject_mapping_css() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
            overflow: visible !important;
            border-radius: 13px !important;
            border: 2px solid rgba(49, 51, 63, 0.18) !important;
            background: rgba(248, 250, 252, 0.92) !important;
            padding: 17px 12px 14px 12px !important;
            margin: 8px 0 12px 0 !important;
            box-shadow: none !important;
            min-height: 104px !important;
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
            top: -9px;
            font-size: 0.85rem;
            line-height: 1.26;
            font-weight: 800;
            color: rgba(49, 51, 63, 0.96);
            margin: 0 0 6px 0 !important;
            padding: 0 !important;
            text-align: left;
            overflow-wrap: normal;
            word-break: normal;
            hyphens: none;
        }

        .bling-map-title-red { color: #dc2626 !important; }
        .bling-map-title-yellow { color: #ca8a04 !important; }
        .bling-map-title-green { color: #16a34a !important; }

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
            min-height: 34px !important;
            height: 34px !important;
            background: #fff3e0 !important;
            border: 1px solid rgba(249, 115, 22, 0.20) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            max-width: 100% !important;
            overflow: hidden !important;
            font-size: 0.85rem !important;
            display: flex !important;
            align-items: center !important;
        }

        div[data-testid="stVerticalBlock"] > div:has(.bling-map-title-red) + div div[data-baseweb="select"] > div {
            background: #fef2f2 !important;
            border-color: rgba(220, 38, 38, 0.30) !important;
        }

        div[data-testid="stVerticalBlock"] > div:has(.bling-map-title-yellow) + div div[data-baseweb="select"] > div {
            background: #fff8db !important;
            border-color: rgba(202, 138, 4, 0.30) !important;
        }

        div[data-testid="stVerticalBlock"] > div:has(.bling-map-title-green) + div div[data-baseweb="select"] > div {
            background: #f0fdf4 !important;
            border-color: rgba(22, 163, 74, 0.30) !important;
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
            color: #2563eb !important;
            font-weight: 700;
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
                padding: 16px 10px 13px 10px !important;
                margin: 7px 0 11px 0 !important;
                border-radius: 13px !important;
                border-width: 2px !important;
                min-height: 102px !important;
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
                top: -9px;
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
                min-height: 34px !important;
                height: 34px !important;
                border-radius: 10px !important;
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
                color: #2563eb !important;
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
