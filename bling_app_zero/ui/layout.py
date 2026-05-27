from __future__ import annotations

import streamlit as st


RESPONSIBLE_FILE = 'bling_app_zero/ui/layout.py'
LAYOUT_STYLE_ID = 'bling-app-layout-style-v1'
TOOLBAR_STYLE_ID = 'bling-toolbar-fix-style-v1'


def inject_streamlit_toolbar_fix() -> None:
    """Ajuste leve para reduzir ruído visual padrão do Streamlit.

    Este módulo é importado diretamente pelo app.py no boot. Por isso ele deve
    ser estável, sem dependências pesadas e sem acessar arquivos externos.
    """
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
    """Injeta o layout visual base do MapeiaAI/IA Planilhas.

    Mantém a Home compacta, cards arredondados e avisos com boa leitura, sem
    alterar a lógica das etapas nem os estados do wizard.
    """
    st.markdown(
        f'''
<style id="{LAYOUT_STYLE_ID}">
.block-container {{
    padding-top: 1.25rem;
    padding-bottom: 2.5rem;
    max-width: 1180px;
}}

section[data-testid="stSidebar"] {{
    border-right: 1px solid rgba(148, 163, 184, 0.25);
}}

h1, h2, h3, h4 {{
    letter-spacing: -0.02em;
}}

[data-testid="stMetric"] {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 0.75rem 0.9rem;
}}

div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 18px;
}}

.stButton > button,
.stDownloadButton > button,
.stLinkButton > a {{
    border-radius: 14px !important;
    font-weight: 750 !important;
}}

.stAlert {{
    border-radius: 14px;
}}

@media (max-width: 768px) {{
    .block-container {{
        padding-left: 0.85rem;
        padding-right: 0.85rem;
        padding-top: 0.75rem;
    }}

    .stButton > button,
    .stDownloadButton > button,
    .stLinkButton > a {{
        min-height: 2.65rem;
    }}
}}
</style>
''',
        unsafe_allow_html=True,
    )


def render_compact_hero() -> None:
    """Renderiza cabeçalho compacto da Home.

    O objetivo é manter a primeira tela objetiva: escolha do tipo de modelo e
    fluxo, sem duplicar seções de Origem dos dados.
    """
    st.markdown(
        '''
<div style="padding:1.05rem 1.15rem;border:1px solid #e2e8f0;border-radius:20px;background:linear-gradient(135deg,#f8fafc,#ffffff);margin-bottom:1rem;">
  <div style="font-size:.82rem;font-weight:900;color:#64748b;text-transform:uppercase;letter-spacing:.08em;">MapeiaAI · Bling</div>
  <div style="font-size:1.55rem;font-weight:950;color:#0f172a;line-height:1.15;margin-top:.25rem;">Modelos, origem, mapeamento e download em um fluxo simples</div>
  <div style="font-size:.98rem;color:#475569;margin-top:.45rem;">Comece escolhendo entre Modelos Bling ou Modelo Universal. A calculadora aparece somente na etapa de preço.</div>
</div>
''',
        unsafe_allow_html=True,
    )


__all__ = ['inject_streamlit_toolbar_fix', 'inject_app_layout', 'render_compact_hero']
