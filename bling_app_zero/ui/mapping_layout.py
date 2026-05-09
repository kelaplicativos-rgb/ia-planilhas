from __future__ import annotations

import html

import streamlit as st


def inject_mapping_css() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
            border-radius: 0 !important;
            border: 0 !important;
            background: transparent !important;
            padding: 8px 0 10px 0 !important;
            margin: 4px 0 12px 0 !important;
            box-shadow: none !important;
            min-height: 0 !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
            gap: 0.28rem !important;
            align-items: center !important;
        }
        .bling-map-title {
            width: min(100%, 560px);
            font-size: 0.84rem;
            line-height: 1.20;
            font-weight: 750;
            color: rgba(49, 51, 63, 0.92);
            margin: 0 auto 3px auto;
            display: block;
            text-align: center;
            overflow-wrap: anywhere;
        }
        .bling-map-title-text {
            min-width: 0;
            overflow-wrap: anywhere;
        }
        .bling-map-help {
            display: none !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] {
            width: min(100%, 560px) !important;
            max-width: 560px !important;
            overflow-x: hidden !important;
            margin: 0 auto !important;
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] label {
            display: none !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] {
            max-width: 100% !important;
            width: 100% !important;
            margin: 0 auto !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
            min-height: 38px !important;
            height: 38px !important;
            background: #eef2f7 !important;
            border: 1px solid rgba(49, 51, 63, 0.10) !important;
            border-radius: 12px !important;
            box-shadow: none !important;
            max-width: 100% !important;
            overflow: hidden !important;
            font-size: 0.84rem !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] span,
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] div {
            max-width: 100% !important;
            overflow-x: hidden !important;
            text-overflow: ellipsis !important;
            line-height: 1.18 !important;
            font-size: 0.84rem !important;
        }
        .bling-map-preview {
            width: min(100%, 560px);
            font-size: 0.80rem;
            line-height: 1.22;
            color: rgba(49, 51, 63, 0.82);
            font-weight: 500;
            padding: 0;
            margin: 3px auto 0 auto;
            border-radius: 0;
            background: transparent;
            border: 0;
            text-align: center;
            overflow-wrap: anywhere;
        }
        @media (max-width: 760px) {
            div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 7px 0 9px 0 !important;
                margin: 3px 0 10px 0 !important;
                border-radius: 0 !important;
                min-height: 0 !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
                gap: 0.24rem !important;
            }
            .bling-map-title {
                width: min(100%, 460px);
                font-size: 0.80rem;
                line-height: 1.18;
                margin-bottom: 3px;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] {
                width: min(100%, 460px) !important;
                max-width: 460px !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
                min-height: 38px !important;
                height: 38px !important;
                border-radius: 11px !important;
                font-size: 0.80rem !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] span,
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] div {
                font-size: 0.80rem !important;
            }
            .bling-map-preview {
                width: min(100%, 460px);
                font-size: 0.76rem;
                line-height: 1.18;
                margin-top: 3px;
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
