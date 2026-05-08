from __future__ import annotations

import html

import streamlit as st


def inject_clean_home_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1180px;
        }
        div[data-testid="stMarkdownContainer"] h1,
        div[data-testid="stMarkdownContainer"] h2,
        div[data-testid="stMarkdownContainer"] h3,
        div[data-testid="stMarkdownContainer"] h4 {
            letter-spacing: -0.02em;
        }
        .bling-hero {
            border: 1px solid rgba(49, 51, 63, 0.10);
            border-radius: 18px;
            padding: 18px 18px 14px 18px;
            margin: 0 0 18px 0;
            background: rgba(250, 250, 250, 0.72);
            overflow: hidden;
        }
        .bling-hero-title {
            font-size: clamp(1.6rem, 6vw, 2.25rem);
            line-height: 1.12;
            font-weight: 800;
            margin: 0 0 8px 0;
            overflow-wrap: anywhere;
        }
        .bling-hero-subtitle {
            font-size: clamp(0.98rem, 3.8vw, 1.08rem);
            line-height: 1.35;
            color: rgba(49, 51, 63, 0.72);
            margin: 0;
            overflow-wrap: anywhere;
        }
        .bling-step-title {
            font-size: 1.16rem;
            line-height: 1.25;
            font-weight: 750;
            margin: 12px 0 6px 0;
            overflow-wrap: anywhere;
        }
        .bling-muted {
            color: rgba(49, 51, 63, 0.65);
            font-size: 0.95rem;
            line-height: 1.35;
            margin-bottom: 0.75rem;
            overflow-wrap: anywhere;
        }
        .bling-compact-note {
            border-radius: 12px;
            padding: 10px 12px;
            background: rgba(240, 242, 246, 0.72);
            color: rgba(49, 51, 63, 0.76);
            font-size: 0.92rem;
            line-height: 1.35;
            margin: 8px 0 14px 0;
            overflow-wrap: anywhere;
        }
        .bling-upload-title {
            font-size: 1.22rem;
            font-weight: 800;
            margin: 10px 0 4px 0;
        }
        .bling-upload-caption {
            color: rgba(49, 51, 63, 0.62);
            font-size: 0.94rem;
            line-height: 1.35;
            margin: 0 0 10px 0;
        }
        div[data-testid="stFileUploader"] section {
            padding: 16px 14px;
        }
        div[data-testid="stFileUploader"] small {
            font-size: 0.82rem;
        }
        @media (max-width: 760px) {
            .main .block-container,
            .block-container {
                padding-left: 0.65rem !important;
                padding-right: 0.65rem !important;
                padding-top: 0.45rem !important;
                padding-bottom: 1rem !important;
                max-width: 100% !important;
            }
            header[data-testid="stHeader"] {
                height: 0 !important;
                min-height: 0 !important;
                visibility: hidden;
            }
            .bling-hero {
                padding: 10px 12px 9px 12px;
                margin: 0 0 10px 0;
                border-radius: 14px;
            }
            .bling-hero-title {
                font-size: 1.22rem;
                line-height: 1.08;
                white-space: normal;
            }
            .bling-hero-subtitle {
                font-size: 0.88rem;
                line-height: 1.25;
            }
            .bling-step-title {
                font-size: 1.02rem;
                line-height: 1.18;
                margin: 8px 0 4px 0;
            }
            .bling-muted {
                font-size: 0.86rem;
                line-height: 1.28;
                margin-bottom: 0.45rem;
            }
            .bling-compact-note {
                padding: 8px 9px;
                margin: 6px 0 10px 0;
                border-radius: 12px;
                font-size: 0.84rem;
                line-height: 1.27;
            }
            div[data-testid="stVerticalBlock"] {
                gap: 0.45rem;
            }
            div[role="radiogroup"] {
                gap: 0.28rem !important;
            }
            div[role="radiogroup"] label {
                border: 1px solid rgba(49, 51, 63, 0.14);
                border-radius: 12px;
                padding: 7px 9px !important;
                background: rgba(250, 250, 250, 0.78);
                margin-bottom: 4px !important;
                width: 100%;
                min-height: 44px;
                align-items: center;
                overflow: hidden;
            }
            div[role="radiogroup"] label > div:first-child {
                margin-right: 0.42rem !important;
                flex: 0 0 auto;
            }
            div[role="radiogroup"] label p,
            div[role="radiogroup"] label span,
            div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
                font-size: 0.93rem !important;
                line-height: 1.18 !important;
                white-space: normal !important;
                overflow-wrap: anywhere !important;
                word-break: normal !important;
                margin: 0 !important;
            }
            div[data-testid="stFileUploader"] section {
                min-height: 104px;
                padding: 12px 10px;
            }
            div[data-testid="stExpander"] details summary p {
                font-size: 0.9rem !important;
                line-height: 1.2 !important;
            }
            .stButton > button,
            .stDownloadButton > button {
                min-height: 42px;
                padding: 0.45rem 0.65rem;
                font-size: 0.92rem;
                white-space: normal;
            }
        }
        @media (max-width: 390px) {
            .main .block-container,
            .block-container {
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
            }
            .bling-hero-title {
                font-size: 1.08rem;
            }
            .bling-hero-subtitle,
            .bling-muted,
            .bling-compact-note {
                font-size: 0.8rem;
            }
            div[role="radiogroup"] label p,
            div[role="radiogroup"] label span,
            div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
                font-size: 0.86rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_compact_hero() -> None:
    st.markdown(
        """
        <div class="bling-hero">
            <div class="bling-hero-title">🚀 IA Planilhas → Bling</div>
            <p class="bling-hero-subtitle">Transforme arquivos, sites e modelos do Bling em CSV pronto para importação.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_step_title(title: str, caption: str | None = None) -> None:
    safe_title = html.escape(str(title or ''))
    st.markdown(f'<div class="bling-step-title">{safe_title}</div>', unsafe_allow_html=True)
    if caption:
        safe_caption = html.escape(str(caption or ''))
        st.markdown(f'<div class="bling-muted">{safe_caption}</div>', unsafe_allow_html=True)


def render_compact_note(text: str) -> None:
    safe_text = html.escape(str(text or ''))
    st.markdown(f'<div class="bling-compact-note">{safe_text}</div>', unsafe_allow_html=True)
