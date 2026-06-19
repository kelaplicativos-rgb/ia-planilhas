from __future__ import annotations

import streamlit as st


RESPONSIBLE_FILE = 'bling_app_zero/ui/layout.py'
LAYOUT_STYLE_ID = 'bling-app-master-layout-style-v5-bus-ride-print'
TOOLBAR_STYLE_ID = 'bling-toolbar-fix-style-v1'


_MASTER_THEME_CSS = '''
:root {
    --bling-bg: #ffffff;
    --bling-bg-strong: #f4f8ff;
    --bling-card: #ffffff;
    --bling-card-soft: #f8fbff;
    --bling-border: #e3e9f2;
    --bling-border-strong: #cfd8e6;
    --bling-text: #031b45;
    --bling-muted: #65738a;
    --bling-muted-strong: #4f6078;
    --bling-soft: #f5f8fc;
    --bling-primary: #087cf5;
    --bling-primary-strong: #0068d9;
    --bling-primary-soft: #eaf4ff;
    --bling-primary-border: #087cf5;
    --bling-success: #087c54;
    --bling-success-soft: #cfffcb;
    --bling-success-border: #a8f2a6;
    --bling-warning: #f59e0b;
    --bling-warning-strong: #9a5b00;
    --bling-warning-soft: #fff8eb;
    --bling-warning-border: #ffe2a9;
    --bling-error: #dc2626;
    --bling-error-soft: #fff1f1;
    --bling-error-border: #ffd1d1;
    --bling-radius-sm: 13px;
    --bling-radius-md: 18px;
    --bling-radius-lg: 24px;
    --bling-shadow-sm: 0 8px 18px rgba(3, 27, 69, 0.045);
    --bling-shadow-md: 0 16px 34px rgba(3, 27, 69, 0.075);
}

html,
body,
[data-testid="stAppViewContainer"] {
    background: var(--bling-bg);
}

[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(180deg, #ffffff 0%, #ffffff 44%, var(--bling-bg-strong) 100%);
}

.block-container {
    max-width: 760px;
    padding-top: 0.72rem;
    padding-bottom: 5.2rem;
}

section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(3, 27, 69, 0.10);
    background: #ffffff;
}

section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span {
    color: var(--bling-muted);
}

h1,
h2,
h3,
h4 {
    letter-spacing: -0.045em;
    color: var(--bling-text);
}

p,
span,
label,
.stCaptionContainer {
    color: var(--bling-muted);
}

a {
    color: var(--bling-primary-strong);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

.stTextInput input,
.stNumberInput input,
.stDateInput input,
.stTimeInput input,
.stTextArea textarea,
[data-baseweb="select"] > div {
    border-radius: 16px !important;
    border-color: var(--bling-border) !important;
    background: #ffffff !important;
    min-height: 3rem !important;
    color: var(--bling-text) !important;
}

.stTextInput input:focus,
.stNumberInput input:focus,
.stDateInput input:focus,
.stTimeInput input:focus,
.stTextArea textarea:focus {
    border-color: var(--bling-primary-border) !important;
    box-shadow: 0 0 0 4px rgba(8, 124, 245, 0.11) !important;
}

[data-testid="stMetric"] {
    background: var(--bling-card);
    border: 1px solid var(--bling-border);
    border-radius: var(--bling-radius-md);
    padding: 0.78rem 0.95rem;
    box-shadow: var(--bling-shadow-sm);
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 20px;
    border-color: var(--bling-border) !important;
    box-shadow: var(--bling-shadow-sm);
    background: var(--bling-card);
}

.stButton > button,
.stDownloadButton > button,
.stLinkButton > a {
    border-radius: 18px !important;
    font-weight: 900 !important;
    min-height: 3rem;
    border: 1px solid var(--bling-border-strong) !important;
    box-shadow: none !important;
    color: var(--bling-text) !important;
    transition: background .16s ease, border-color .16s ease, transform .16s ease, box-shadow .16s ease;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
.stLinkButton > a:hover {
    border-color: var(--bling-primary-border) !important;
    background: var(--bling-primary-soft) !important;
    transform: translateY(-1px);
    box-shadow: 0 8px 18px rgba(8, 124, 245, 0.10) !important;
}

.stButton > button:disabled,
.stDownloadButton > button:disabled {
    opacity: .58 !important;
    cursor: not-allowed !important;
    transform: none !important;
}

.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: var(--bling-primary) !important;
    color: #ffffff !important;
    border-color: var(--bling-primary) !important;
    box-shadow: 0 12px 24px rgba(8, 124, 245, 0.22) !important;
}

.stLinkButton > a {
    text-decoration: none !important;
}

.stAlert {
    border-radius: var(--bling-radius-md);
    border-width: 1px;
    box-shadow: var(--bling-shadow-sm);
}

.stAlert [data-testid="stMarkdownContainer"] p {
    color: inherit;
}

[data-testid="stAlert"] {
    border-radius: var(--bling-radius-md);
    border: 1px solid var(--bling-border);
    box-shadow: var(--bling-shadow-sm);
}

[data-testid="stAlert"] div,
[data-testid="stAlert"] p,
[data-testid="stAlert"] span {
    color: inherit;
}

[data-testid="stAlert"][kind="warning"],
[data-testid="stAlert"][data-baseweb="notification"]:has(svg) {
    background: var(--bling-warning-soft) !important;
    border-color: var(--bling-warning-border) !important;
    color: var(--bling-warning-strong) !important;
}

[data-testid="stAlert"][kind="error"] {
    background: var(--bling-error-soft) !important;
    border-color: var(--bling-error-border) !important;
    color: var(--bling-error) !important;
}

[data-testid="stAlert"][kind="success"] {
    background: var(--bling-success-soft) !important;
    border-color: var(--bling-success-border) !important;
    color: var(--bling-success) !important;
}

[data-testid="stExpander"] {
    border: 1px solid var(--bling-border);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.94);
}

[data-testid="stExpander"] details summary {
    color: var(--bling-text);
    font-weight: 850;
}

[data-testid="stFileUploader"] {
    border-radius: var(--bling-radius-md);
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--bling-border);
    border-radius: var(--bling-radius-md);
    overflow: hidden;
    box-shadow: var(--bling-shadow-sm);
}

.bling-home-eyebrow {
    font-size: .78rem !important;
    font-weight: 900 !important;
    color: var(--bling-primary-strong) !important;
    text-transform: none !important;
    letter-spacing: .01em !important;
}

.bling-home-hero {
    padding: 1.15rem 1.05rem !important;
    border: 3px solid var(--bling-primary) !important;
    border-radius: 26px !important;
    background: #ffffff !important;
    margin: .35rem 0 1rem 0 !important;
    box-shadow: 0 12px 26px rgba(3, 27, 69, 0.08) !important;
}

.bling-home-title {
    color: var(--bling-text) !important;
    font-size: clamp(2rem, 6.2vw, 2.95rem) !important;
    font-weight: 950 !important;
    line-height: 1.07 !important;
    letter-spacing: -0.055em !important;
    margin-top: .45rem !important;
    max-width: 760px !important;
}

.bling-home-subtitle {
    color: var(--bling-muted) !important;
    font-size: 1.02rem !important;
    line-height: 1.38 !important;
    margin-top: .66rem !important;
    max-width: 720px !important;
    font-weight: 650 !important;
}

.bling-step-pills {
    display: flex;
    flex-wrap: wrap;
    gap: .42rem;
    margin-top: .9rem;
}

.bling-step-pill {
    border: 1px solid rgba(8, 124, 245, 0.24);
    background: var(--bling-primary-soft);
    color: var(--bling-primary-strong);
    border-radius: 999px;
    padding: .36rem .66rem;
    font-size: .76rem;
    font-weight: 900;
}

.bling-home-section-title {
    color: var(--bling-text) !important;
    font-size: 1.18rem;
    font-weight: 950;
    margin: .35rem 0 .18rem 0;
}

.bling-home-section-subtitle {
    color: var(--bling-muted) !important;
    font-size: .95rem;
    line-height: 1.42;
    margin-bottom: .82rem;
}

.bling-home-card {
    border: 1px solid var(--bling-border) !important;
    background: #ffffff !important;
    border-radius: 20px !important;
    box-shadow: var(--bling-shadow-sm) !important;
}

.bling-home-alert {
    border: 1px solid var(--bling-warning-border) !important;
    background: var(--bling-warning-soft) !important;
    color: var(--bling-warning-strong) !important;
    border-radius: 18px !important;
}

.bling-mini-note {
    color: var(--bling-muted);
    font-size: .83rem;
    margin-top: .8rem;
}

.bling-attention-card {
    background: var(--bling-warning-soft);
    border: 1px solid var(--bling-warning-border);
    border-radius: var(--bling-radius-md);
    color: var(--bling-warning-strong);
    padding: .85rem .95rem;
    box-shadow: var(--bling-shadow-sm);
}

.bling-attention-card strong,
.bling-attention-card p,
.bling-attention-card span {
    color: var(--bling-warning-strong);
}

.bling-topline {
    display: flex;
    align-items: center;
    gap: .55rem;
    margin: 0 0 .55rem 0;
    color: var(--bling-text);
    font-size: .9rem;
    font-weight: 950;
}

.bling-topline-dot {
    width: .58rem;
    height: .58rem;
    border-radius: 999px;
    background: var(--bling-primary);
    display: inline-block;
}

@media (max-width: 768px) {
    .block-container {
        max-width: 100vw;
        padding-left: 0.78rem;
        padding-right: 0.78rem;
        padding-top: 0.62rem;
    }

    .bling-home-hero {
        padding: 1rem .95rem !important;
        border-radius: 24px !important;
    }

    .bling-home-title {
        font-size: clamp(2rem, 9vw, 2.55rem) !important;
    }

    .bling-home-subtitle {
        font-size: .94rem !important;
    }

    .stButton > button,
    .stDownloadButton > button,
    .stLinkButton > a {
        min-height: 3.05rem;
        width: 100%;
    }
}
'''


def inject_streamlit_toolbar_fix() -> None:
    """Ajuste mínimo que preserva o menu nativo do Streamlit."""
    st.markdown(
        f'''
<style id="{TOOLBAR_STYLE_ID}">
[data-testid="stToolbar"] {{
    right: 0.75rem;
}}
[data-testid="stDecoration"] {{
    display: none;
}}
footer {{
    visibility: hidden;
}}
</style>
''',
        unsafe_allow_html=True,
    )


def inject_app_layout() -> None:
    """Injeta o tema global com paleta inspirada no print de app de viagem."""
    st.markdown(
        f'''
<style id="{LAYOUT_STYLE_ID}">
{_MASTER_THEME_CSS}
</style>
''',
        unsafe_allow_html=True,
    )


def render_compact_hero() -> None:
    """Renderiza cabeçalho compacto inspirado em apps mobile de etapas."""
    st.markdown(
        '''
<div class="bling-topline"><span class="bling-topline-dot"></span><span>MapeiaAI · Bling</span></div>
<div class="bling-home-hero">
  <div class="bling-home-eyebrow">Olá! Fluxo simples por etapas</div>
  <div class="bling-home-title">Mapeie inteligente: arquivo, site ou Bling com economia de tempo.</div>
  <div class="bling-home-subtitle">Escolha a origem, revise os dados, confirme o modelo e finalize com arquivo pronto ou envio ao Bling.</div>
  <div class="bling-step-pills">
    <span class="bling-step-pill">1. Origem</span>
    <span class="bling-step-pill">2. Dados</span>
    <span class="bling-step-pill">3. Modelo</span>
    <span class="bling-step-pill">4. Revisão</span>
    <span class="bling-step-pill">5. Saída</span>
  </div>
</div>
''',
        unsafe_allow_html=True,
    )


__all__ = ['inject_app_layout', 'inject_streamlit_toolbar_fix', 'render_compact_hero']
