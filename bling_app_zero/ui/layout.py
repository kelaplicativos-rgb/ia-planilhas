from __future__ import annotations

import streamlit as st


RESPONSIBLE_FILE = 'bling_app_zero/ui/layout.py'
LAYOUT_STYLE_ID = 'bling-app-master-layout-style-v3'
TOOLBAR_STYLE_ID = 'bling-toolbar-fix-style-v1'


_MASTER_THEME_CSS = '''
:root {
    --bling-bg: #f8fafc;
    --bling-bg-strong: #eef6ff;
    --bling-card: #ffffff;
    --bling-card-soft: #f9fbff;
    --bling-border: #e2e8f0;
    --bling-border-strong: #cbd5e1;
    --bling-text: #0f172a;
    --bling-muted: #64748b;
    --bling-muted-strong: #475569;
    --bling-soft: #f1f5f9;
    --bling-primary: #2563eb;
    --bling-primary-strong: #1d4ed8;
    --bling-primary-soft: #eff6ff;
    --bling-primary-border: #bfdbfe;
    --bling-success: #16a34a;
    --bling-success-soft: #ecfdf5;
    --bling-success-border: #bbf7d0;
    --bling-warning: #f97316;
    --bling-warning-strong: #c2410c;
    --bling-warning-soft: #fff7ed;
    --bling-warning-border: #fed7aa;
    --bling-error: #dc2626;
    --bling-error-soft: #fef2f2;
    --bling-error-border: #fecaca;
    --bling-radius-sm: 12px;
    --bling-radius-md: 16px;
    --bling-radius-lg: 22px;
    --bling-shadow-sm: 0 8px 20px rgba(15, 23, 42, 0.045);
    --bling-shadow-md: 0 14px 34px rgba(15, 23, 42, 0.06);
}

html,
body,
[data-testid="stAppViewContainer"] {
    background: var(--bling-bg);
}

[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(180deg, #ffffff 0%, var(--bling-bg) 30%, var(--bling-bg) 100%);
}

.block-container {
    padding-top: 1.05rem;
    padding-bottom: 2.25rem;
    max-width: 1120px;
}

section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(148, 163, 184, 0.22);
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
    letter-spacing: -0.025em;
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
    box-shadow: var(--bling-shadow-md);
    background: var(--bling-card);
}

.stButton > button,
.stDownloadButton > button,
.stLinkButton > a {
    border-radius: 13px !important;
    font-weight: 760 !important;
    min-height: 2.65rem;
    border-color: #dbe3ef !important;
    box-shadow: none !important;
    transition: background .16s ease, border-color .16s ease, transform .16s ease;
}

.stButton > button:hover,
.stDownloadButton > button:hover,
.stLinkButton > a:hover {
    border-color: #93c5fd !important;
    background: var(--bling-primary-soft) !important;
    transform: translateY(-1px);
}

.stButton > button:disabled,
.stDownloadButton > button:disabled {
    opacity: .62 !important;
    cursor: not-allowed !important;
    transform: none !important;
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
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.78);
}

[data-testid="stExpander"] details summary {
    color: var(--bling-text);
    font-weight: 760;
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
    color: var(--bling-muted-strong);
    text-transform: uppercase;
    letter-spacing: .12em;
}

.bling-home-hero {
    padding: 1.15rem 1.2rem;
    border: 1px solid var(--bling-border);
    border-radius: var(--bling-radius-lg);
    background: linear-gradient(135deg, #ffffff 0%, var(--bling-card-soft) 58%, var(--bling-bg-strong) 100%);
    margin-bottom: 1rem;
    box-shadow: 0 18px 42px rgba(15, 23, 42, 0.055);
}

.bling-home-title {
    color: var(--bling-text);
    font-size: clamp(1.45rem, 3.5vw, 2rem);
    font-weight: 950;
    line-height: 1.08;
    margin-top: .34rem;
    max-width: 760px;
}

.bling-home-subtitle {
    color: var(--bling-muted);
    font-size: 1rem;
    line-height: 1.55;
    margin-top: .55rem;
    max-width: 820px;
}

.bling-step-pills {
    display: flex;
    flex-wrap: wrap;
    gap: .45rem;
    margin-top: .9rem;
}

.bling-step-pill {
    border: 1px solid var(--bling-primary-border);
    background: rgba(239, 246, 255, .86);
    color: #1e3a8a;
    border-radius: 999px;
    padding: .34rem .62rem;
    font-size: .78rem;
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

@media (max-width: 768px) {
    .block-container {
        padding-left: 0.85rem;
        padding-right: 0.85rem;
        padding-top: 0.75rem;
    }

    .bling-home-hero {
        padding: 1rem;
        border-radius: 18px;
    }

    .bling-home-title {
        font-size: 1.35rem;
    }

    .stButton > button,
    .stDownloadButton > button,
    .stLinkButton > a {
        min-height: 2.8rem;
        width: 100%;
    }
}
'''


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
    """Injeta o tema mestre global, profissional, leve e responsivo."""
    st.markdown(
        f'''
<style id="{LAYOUT_STYLE_ID}">
{_MASTER_THEME_CSS}
</style>
''',
        unsafe_allow_html=True,
    )


def render_compact_hero() -> None:
    """Renderiza cabeçalho compacto alinhado ao tema mestre."""
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
