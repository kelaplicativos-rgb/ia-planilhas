from __future__ import annotations

import streamlit as st


RESPONSIBLE_FILE = 'bling_app_zero/ui/layout.py'
LAYOUT_STYLE_ID = 'bling-app-master-layout-style-v4-minimal-steps'
TOOLBAR_STYLE_ID = 'bling-toolbar-fix-style-v1'


_MASTER_THEME_CSS = '''
:root {
    --bling-bg: #fbfcff;
    --bling-bg-strong: #eef7ff;
    --bling-card: #ffffff;
    --bling-card-soft: #f7fbff;
    --bling-border: #e6edf5;
    --bling-border-strong: #d8e4f0;
    --bling-text: #111827;
    --bling-muted: #6b7280;
    --bling-muted-strong: #4b5563;
    --bling-soft: #f4f8fc;
    --bling-primary: #1683ef;
    --bling-primary-strong: #0f6fd0;
    --bling-primary-soft: #eaf5ff;
    --bling-primary-border: #b9dcff;
    --bling-success: #0f9f6e;
    --bling-success-soft: #edfff8;
    --bling-success-border: #bfefdc;
    --bling-warning: #f59e0b;
    --bling-warning-strong: #9a5b00;
    --bling-warning-soft: #fff8eb;
    --bling-warning-border: #ffe2a9;
    --bling-error: #dc2626;
    --bling-error-soft: #fff1f1;
    --bling-error-border: #ffd1d1;
    --bling-radius-sm: 12px;
    --bling-radius-md: 16px;
    --bling-radius-lg: 22px;
    --bling-shadow-sm: 0 6px 16px rgba(17, 24, 39, 0.035);
    --bling-shadow-md: 0 10px 26px rgba(17, 24, 39, 0.055);
}

html,
body,
[data-testid="stAppViewContainer"] {
    background: var(--bling-bg);
}

[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(180deg, #ffffff 0%, var(--bling-bg) 28%, var(--bling-bg) 100%);
}

.block-container {
    max-width: 780px;
    padding-top: 0.82rem;
    padding-bottom: 5rem;
}

section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(148, 163, 184, 0.18);
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
    letter-spacing: -0.03em;
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
    border-radius: 15px !important;
    border-color: var(--bling-border) !important;
    background: #ffffff !important;
    min-height: 2.85rem !important;
}

.stTextInput input:focus,
.stNumberInput input:focus,
.stDateInput input:focus,
.stTimeInput input:focus,
.stTextArea textarea:focus {
    border-color: var(--bling-primary-border) !important;
    box-shadow: 0 0 0 3px rgba(22, 131, 239, 0.10) !important;
}

[data-testid="stMetric"] {
    background: var(--bling-card);
    border: 1px solid var(--bling-border);
    border-radius: var(--bling-radius-md);
    padding: 0.75rem 0.9rem;
    box-shadow: var(--bling-shadow-sm);
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px;
    border-color: var(--bling-border) !important;
    box-shadow: var(--bling-shadow-sm);
    background: var(--bling-card);
}

.stButton > button,
.stDownloadButton > button,
.stLinkButton > a {
    border-radius: 999px !important;
    font-weight: 850 !important;
    min-height: 2.85rem;
    border: 1px solid var(--bling-border-strong) !important;
    box-shadow: none !important;
    transition: background .16s ease, border-color .16s ease, transform .16s ease;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
.stLinkButton > a:hover {
    border-color: var(--bling-primary-border) !important;
    background: var(--bling-primary-soft) !important;
    transform: translateY(-1px);
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
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.82);
}

[data-testid="stExpander"] details summary {
    color: var(--bling-text);
    font-weight: 800;
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
    font-size: .74rem;
    font-weight: 900;
    color: var(--bling-primary-strong);
    text-transform: uppercase;
    letter-spacing: .11em;
}

.bling-home-hero {
    padding: 1rem 1.05rem;
    border: 1px solid var(--bling-border);
    border-radius: var(--bling-radius-lg);
    background: linear-gradient(135deg, #ffffff 0%, var(--bling-card-soft) 70%, var(--bling-bg-strong) 100%);
    margin-bottom: .85rem;
    box-shadow: var(--bling-shadow-sm);
}

.bling-home-title {
    color: var(--bling-text);
    font-size: clamp(1.35rem, 3.8vw, 1.88rem);
    font-weight: 950;
    line-height: 1.08;
    margin-top: .34rem;
    max-width: 760px;
}

.bling-home-subtitle {
    color: var(--bling-muted);
    font-size: .96rem;
    line-height: 1.45;
    margin-top: .52rem;
    max-width: 760px;
}

.bling-step-pills {
    display: flex;
    flex-wrap: wrap;
    gap: .42rem;
    margin-top: .82rem;
}

.bling-step-pill {
    border: 1px solid var(--bling-primary-border);
    background: rgba(234, 245, 255, .86);
    color: #075985;
    border-radius: 999px;
    padding: .34rem .62rem;
    font-size: .76rem;
    font-weight: 850;
}

.bling-home-section-title {
    color: var(--bling-text);
    font-size: 1.15rem;
    font-weight: 920;
    margin: .25rem 0 .2rem 0;
}

.bling-home-section-subtitle {
    color: var(--bling-muted);
    font-size: .94rem;
    line-height: 1.45;
    margin-bottom: .8rem;
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
    color: var(--bling-muted-strong);
    font-size: .84rem;
    font-weight: 850;
}

.bling-topline-dot {
    width: .52rem;
    height: .52rem;
    border-radius: 999px;
    background: var(--bling-primary);
    display: inline-block;
}

@media (max-width: 768px) {
    .block-container {
        max-width: 100vw;
        padding-left: 0.78rem;
        padding-right: 0.78rem;
        padding-top: 0.64rem;
    }

    .bling-home-hero {
        padding: .95rem;
        border-radius: 18px;
    }

    .bling-home-title {
        font-size: 1.34rem;
    }

    .bling-home-subtitle {
        font-size: .9rem;
    }

    .stButton > button,
    .stDownloadButton > button,
    .stLinkButton > a {
        min-height: 2.95rem;
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
    """Injeta o tema mestre global, leve, minimalista e responsivo."""
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
  <div class="bling-home-eyebrow">Fluxo simples por etapas</div>
  <div class="bling-home-title">Prepare, revise e finalize sem trocar de caminho.</div>
  <div class="bling-home-subtitle">Interface leve para celular: escolha a origem, carregue os dados, confirme o mapeamento e finalize em arquivo ou Bling.</div>
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
