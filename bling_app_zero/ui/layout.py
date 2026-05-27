from __future__ import annotations

import streamlit as st


RESPONSIBLE_FILE = 'bling_app_zero/ui/layout.py'
LAYOUT_STYLE_ID = 'bling-app-layout-style-v2'
TOOLBAR_STYLE_ID = 'bling-toolbar-fix-style-v1'


def inject_streamlit_toolbar_fix() -> None:
    """Ajuste leve para reduzir ruído visual padrão do Streamlit."""
    st.markdown(
        f'''
<style id="{TOOLBAR_STYLE_ID}">
[data-testid="stToolbar"] {{
    right: 0.75rem;
}}
[data-testid="stDecoration"] {{
    display: none;
}}
#MainMenu {{
    visibility: hidden;
}}
footer {{
    visibility: hidden;
}}
</style>
''',
        unsafe_allow_html=True,
    )


def inject_app_layout() -> None:
    """Injeta layout profissional, leve e responsivo sem alterar o fluxo."""
    st.markdown(
        f'''
<style id="{LAYOUT_STYLE_ID}">
:root {{
    --bling-bg: #f8fafc;
    --bling-card: #ffffff;
    --bling-border: #e5e7eb;
    --bling-text: #0f172a;
    --bling-muted: #64748b;
    --bling-soft: #f1f5f9;
    --bling-primary: #1d4ed8;
    --bling-primary-soft: #eff6ff;
}}

html, body, [data-testid="stAppViewContainer"] {{
    background: var(--bling-bg);
}}

.block-container {{
    padding-top: 1.05rem;
    padding-bottom: 2.25rem;
    max-width: 1040px;
}}

section[data-testid="stSidebar"] {{
    border-right: 1px solid rgba(148, 163, 184, 0.22);
    background: #ffffff;
}}

h1, h2, h3, h4 {{
    letter-spacing: -0.025em;
    color: var(--bling-text);
}}

p, span, label, .stCaptionContainer {{
    color: var(--bling-muted);
}}

[data-testid="stMetric"] {{
    background: var(--bling-card);
    border: 1px solid var(--bling-border);
    border-radius: 16px;
    padding: 0.75rem 0.9rem;
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.035);
}}

div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 18px;
    border-color: var(--bling-border) !important;
    box-shadow: 0 14px 34px rgba(15, 23, 42, 0.045);
    background: var(--bling-card);
}}

.stButton > button,
.stDownloadButton > button,
.stLinkButton > a {{
    border-radius: 13px !important;
    font-weight: 760 !important;
    min-height: 2.65rem;
    border-color: #dbe3ef !important;
    box-shadow: none !important;
}}

.stButton > button:hover,
.stDownloadButton > button:hover,
.stLinkButton > a:hover {{
    border-color: #93c5fd !important;
    background: var(--bling-primary-soft) !important;
}}

.stAlert {{
    border-radius: 14px;
    border-width: 1px;
}}

[data-testid="stExpander"] {{
    border: 1px solid var(--bling-border);
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.72);
}}

.bling-home-eyebrow {{
    font-size: .74rem;
    font-weight: 900;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: .12em;
}}

.bling-home-hero {{
    padding: 1.15rem 1.2rem;
    border: 1px solid var(--bling-border);
    border-radius: 22px;
    background: linear-gradient(135deg, #ffffff 0%, #f8fafc 58%, #eef6ff 100%);
    margin-bottom: 1rem;
    box-shadow: 0 18px 42px rgba(15, 23, 42, 0.055);
}}

.bling-home-title {{
    color: var(--bling-text);
    font-size: clamp(1.45rem, 3.5vw, 2rem);
    font-weight: 950;
    line-height: 1.08;
    margin-top: .34rem;
    max-width: 760px;
}}

.bling-home-subtitle {{
    color: var(--bling-muted);
    font-size: 1rem;
    line-height: 1.55;
    margin-top: .55rem;
    max-width: 820px;
}}

.bling-step-pills {{
    display: flex;
    flex-wrap: wrap;
    gap: .45rem;
    margin-top: .9rem;
}}

.bling-step-pill {{
    border: 1px solid #dbeafe;
    background: rgba(239, 246, 255, .82);
    color: #1e3a8a;
    border-radius: 999px;
    padding: .34rem .62rem;
    font-size: .78rem;
    font-weight: 850;
}}

.bling-home-section-title {{
    color: var(--bling-text);
    font-size: 1.15rem;
    font-weight: 920;
    margin: .25rem 0 .2rem 0;
}}

.bling-home-section-subtitle {{
    color: var(--bling-muted);
    font-size: .94rem;
    line-height: 1.45;
    margin-bottom: .8rem;
}}

.bling-mini-note {{
    color: var(--bling-muted);
    font-size: .83rem;
    margin-top: .8rem;
}}

@media (max-width: 768px) {{
    .block-container {{
        padding-left: 0.85rem;
        padding-right: 0.85rem;
        padding-top: 0.75rem;
    }}

    .bling-home-hero {{
        padding: 1rem;
        border-radius: 18px;
    }}

    .bling-home-title {{
        font-size: 1.35rem;
    }}

    .stButton > button,
    .stDownloadButton > button,
    .stLinkButton > a {{
        min-height: 2.8rem;
    }}
}}
</style>
''',
        unsafe_allow_html=True,
    )


def render_compact_hero() -> None:
    """Renderiza cabeçalho compacto e profissional da Home."""
    st.markdown(
        '''
<div class="bling-home-hero">
  <div class="bling-home-eyebrow">MapeiaAI · Bling</div>
  <div class="bling-home-title">Prepare planilhas para o Bling com menos cliques.</div>
  <div class="bling-home-subtitle">Escolha um modelo, carregue a origem dos dados, revise o mapeamento e baixe o arquivo final pronto para importar.</div>
  <div class="bling-step-pills">
    <span class="bling-step-pill">1. Modelo</span>
    <span class="bling-step-pill">2. Origem</span>
    <span class="bling-step-pill">3. Mapeamento</span>
    <span class="bling-step-pill">4. Download</span>
  </div>
</div>
''',
        unsafe_allow_html=True,
    )


__all__ = ['inject_streamlit_toolbar_fix', 'inject_app_layout', 'render_compact_hero']
