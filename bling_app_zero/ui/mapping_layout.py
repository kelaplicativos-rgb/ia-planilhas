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
            border-radius: 12px !important;
            border: 1px solid rgba(49, 51, 63, 0.13) !important;
            background: rgba(248, 250, 252, 0.92) !important;
            padding: 7px 10px 7px 10px !important;
            margin: 6px 0 8px 0 !important;
            box-shadow: none !important;
            min-height: unset !important;
            height: auto !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
            gap: 0.14rem !important;
            overflow: visible !important;
        }

        .bling-map-title {
            width: 100%;
            display: block;
            position: static;
            font-size: 0.82rem;
            line-height: 1.12;
            font-weight: 800;
            color: rgba(49, 51, 63, 0.96);
            margin: 0 0 3px 0 !important;
            padding: 0 !important;
            text-align: left;
            overflow-wrap: anywhere;
            word-break: normal;
        }

        .bling-map-title-text {
            display: inline;
            min-width: 0;
            overflow-wrap: anywhere;
        }

        .bling-map-help {
            display: none !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] {
            display: block !important;
            position: static !important;
            width: 100% !important;
            max-width: 100% !important;
            overflow: visible !important;
            margin: 0 0 2px 0 !important;
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
            min-height: 32px !important;
            height: 32px !important;
            background: #eef2f7 !important;
            border: 1px solid rgba(49, 51, 63, 0.12) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
            max-width: 100% !important;
            overflow: hidden !important;
            font-size: 0.82rem !important;
            display: flex !important;
            align-items: center !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] span {
            max-width: 100% !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            line-height: 1.10 !important;
            font-size: 0.82rem !important;
        }

        .bling-map-preview {
            display: block;
            position: static;
            width: 100%;
            font-size: 0.73rem;
            line-height: 1.16;
            color: #118a32;
            font-weight: 700;
            padding: 0;
            margin: 1px 0 0 0 !important;
            border-radius: 0;
            background: transparent;
            border: 0;
            text-align: left;
            overflow-wrap: anywhere;
            word-break: normal;
        }

        @media (max-width: 760px) {
            div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 6px 8px 6px 8px !important;
                margin: 5px 0 7px 0 !important;
                border-radius: 12px !important;
                min-height: unset !important;
                height: auto !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
                gap: 0.10rem !important;
            }

            .bling-map-title {
                font-size: 0.80rem;
                line-height: 1.10;
                margin: 0 0 2px 0 !important;
                padding: 0 !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] {
                margin: 0 0 1px 0 !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
                min-height: 31px !important;
                height: 31px !important;
                border-radius: 9px !important;
                font-size: 0.80rem !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] span {
                font-size: 0.80rem !important;
                line-height: 1.08 !important;
            }

            .bling-map-preview {
                font-size: 0.72rem;
                line-height: 1.15;
                margin: 1px 0 0 0 !important;
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
