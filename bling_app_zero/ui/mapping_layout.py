from __future__ import annotations

import html

import streamlit as st


def inject_mapping_css() -> None:
    st.markdown(
        """
        <style>
        /* CSS exclusivo do mapeamento manual. Não fica no layout global. */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
            border-radius: 13px !important;
            border: 1px solid rgba(49, 51, 63, 0.12) !important;
            background: rgba(248, 250, 252, 0.94) !important;
            padding: 7px 8px 6px 8px !important;
            margin: 3px 0 6px 0 !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.035) !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
            gap: 0.12rem !important;
        }
        .bling-map-title {
            font-size: 0.88rem;
            line-height: 1.10;
            font-weight: 800;
            color: rgba(49, 51, 63, 0.95);
            margin: 0 0 2px 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 6px;
            overflow-wrap: anywhere;
        }
        .bling-map-title-text {
            min-width: 0;
            overflow-wrap: anywhere;
        }
        .bling-map-help {
            opacity: 0.62;
            flex: 0 0 auto;
        }
        .bling-map-preview {
            font-size: 0.70rem;
            line-height: 1.05;
            color: #118a32;
            font-weight: 750;
            padding: 2px 5px;
            margin: 0;
            border-radius: 7px;
            background: rgba(232, 247, 238, 0.62);
            border: 1px solid rgba(17, 138, 50, 0.08);
            overflow-wrap: anywhere;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] {
            padding: 0 !important;
            margin: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
            max-width: 100% !important;
            overflow-x: hidden !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] label {
            display: none !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] {
            max-width: 100% !important;
            width: 100% !important;
            margin: 0 !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
            min-height: 39px !important;
            background: #eef2f7 !important;
            border: 1px solid rgba(49, 51, 63, 0.11) !important;
            border-radius: 11px !important;
            box-shadow: none !important;
            max-width: 100% !important;
            overflow: hidden !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] span,
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] div {
            max-width: 100% !important;
            overflow-x: hidden !important;
            text-overflow: ellipsis !important;
        }

        @media (max-width: 760px) {
            div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 6px 7px 5px 7px !important;
                margin: 2px 0 5px 0 !important;
                border-radius: 12px !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
                gap: 0.08rem !important;
            }
            .bling-map-title {
                font-size: 0.82rem;
                margin-bottom: 1px;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
                min-height: 38px !important;
            }
            .bling-map-preview {
                font-size: 0.66rem;
                line-height: 1.02;
                padding: 1px 4px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_mapping_title(target_label: str) -> None:
    safe = html.escape(str(target_label or ''))
    st.markdown(
        f'<div class="bling-map-title"><span class="bling-map-title-text">{safe}</span><span class="bling-map-help">?</span></div>',
        unsafe_allow_html=True,
    )


def render_mapping_preview(text: str) -> None:
    safe = html.escape(str(text or '').strip())
    if not safe:
        return
    st.markdown(f'<div class="bling-map-preview">{safe}</div>', unsafe_allow_html=True)
