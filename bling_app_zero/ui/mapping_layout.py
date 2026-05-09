from __future__ import annotations

import html

import streamlit as st


def inject_mapping_css() -> None:
    st.markdown(
        """
        <style>
        /* CSS exclusivo do mapeamento manual.
           Card externo confortável + select central menor + preview legível. */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
            border-radius: 15px !important;
            border: 1px solid rgba(49, 51, 63, 0.13) !important;
            background: rgba(248, 250, 252, 0.96) !important;
            padding: 13px 10px 10px 10px !important;
            margin: 8px 0 12px 0 !important;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
            gap: 0.18rem !important;
        }
        .bling-map-title {
            font-size: 0.88rem;
            line-height: 1.14;
            font-weight: 800;
            color: rgba(49, 51, 63, 0.95);
            margin: 0 0 4px 0;
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
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] {
            max-width: 100% !important;
            overflow-x: hidden !important;
            margin: 0 !important;
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
            margin: 0 !important;
        }
        /* Campo selecionável do meio menor para não esmagar título e preview. */
        div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
            min-height: 34px !important;
            height: 34px !important;
            background: #eef2f7 !important;
            border: 1px solid rgba(49, 51, 63, 0.11) !important;
            border-radius: 10px !important;
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
        .bling-map-preview {
            font-size: 0.70rem;
            line-height: 1.08;
            color: #118a32;
            font-weight: 750;
            padding: 3px 5px;
            margin: 4px 0 0 0;
            border-radius: 7px;
            background: rgba(232, 247, 238, 0.70);
            border: 1px solid rgba(17, 138, 50, 0.08);
            overflow-wrap: anywhere;
        }

        @media (max-width: 760px) {
            div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 12px 9px 9px 9px !important;
                margin: 7px 0 11px 0 !important;
                border-radius: 14px !important;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
                gap: 0.14rem !important;
            }
            .bling-map-title {
                font-size: 0.83rem;
                line-height: 1.10;
                margin-bottom: 3px;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] div[data-baseweb="select"] > div {
                min-height: 33px !important;
                height: 33px !important;
                border-radius: 10px !important;
            }
            .bling-map-preview {
                font-size: 0.66rem;
                line-height: 1.04;
                padding: 2px 4px;
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
