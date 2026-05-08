from __future__ import annotations

import streamlit as st


def inject_clean_home_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
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
        }
        .bling-hero-title {
            font-size: clamp(1.6rem, 6vw, 2.25rem);
            line-height: 1.12;
            font-weight: 800;
            margin: 0 0 8px 0;
        }
        .bling-hero-subtitle {
            font-size: clamp(0.98rem, 3.8vw, 1.08rem);
            line-height: 1.35;
            color: rgba(49, 51, 63, 0.72);
            margin: 0;
        }
        .bling-step-title {
            font-size: 1.16rem;
            line-height: 1.25;
            font-weight: 750;
            margin: 12px 0 6px 0;
        }
        .bling-muted {
            color: rgba(49, 51, 63, 0.65);
            font-size: 0.95rem;
            line-height: 1.35;
            margin-bottom: 0.75rem;
        }
        .bling-compact-note {
            border-radius: 12px;
            padding: 10px 12px;
            background: rgba(240, 242, 246, 0.72);
            color: rgba(49, 51, 63, 0.76);
            font-size: 0.92rem;
            line-height: 1.35;
            margin: 8px 0 14px 0;
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
        @media (max-width: 640px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 0.7rem;
            }
            .bling-hero {
                padding: 14px 14px 12px 14px;
                margin-bottom: 14px;
                border-radius: 16px;
            }
            .bling-hero-title {
                font-size: 1.55rem;
            }
            .bling-hero-subtitle {
                font-size: 0.96rem;
            }
            div[role="radiogroup"] {
                gap: 0.35rem;
            }
            div[role="radiogroup"] label {
                border: 1px solid rgba(49, 51, 63, 0.14);
                border-radius: 14px;
                padding: 10px 12px;
                background: rgba(250, 250, 250, 0.78);
                margin-bottom: 6px;
                width: 100%;
            }
            div[data-testid="stFileUploader"] section {
                min-height: 132px;
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
    st.markdown(f'<div class="bling-step-title">{title}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="bling-muted">{caption}</div>', unsafe_allow_html=True)


def render_compact_note(text: str) -> None:
    st.markdown(f'<div class="bling-compact-note">{text}</div>', unsafe_allow_html=True)
