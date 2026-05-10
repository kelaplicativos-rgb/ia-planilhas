from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.rules_resources_tab import render_resources_tab
from bling_app_zero.ui.rules_user_tab import render_user_rules_tab

FINAL_STEPS = {'preview', 'download', 'final'}
FINAL_DF_KEYS = (
    'df_final',
    'df_final_cadastro',
    'df_final_estoque',
    'cadastro_wizard_df_final',
    'estoque_wizard_df_final',
)


def _current_flow_step() -> str:
    """Retorna a etapa atual do wizard sem depender de import do home_wizard."""
    return str(
        st.session_state.get('bling_wizard_step')
        or st.session_state.get('etapa_fluxo')
        or st.session_state.get('etapa')
        or ''
    ).strip().lower()


def _has_final_dataframe() -> bool:
    """Detecta se já existe uma base final/pre-final carregada na sessão."""
    for key in FINAL_DF_KEYS:
        value = st.session_state.get(key)
        if value is None or not hasattr(value, 'columns'):
            continue
        try:
            if len(value.columns) > 0:
                return True
        except Exception:
            continue
    return False


def _should_render_rules_panel() -> bool:
    """Mostra o painel somente quando ele ajuda no fluxo final.

    O painel de regras/recursos é uma ferramenta de conferência do CSV final.
    Fora de preview/download ele vira ruído visual e parecia componente vazio.
    """
    step = _current_flow_step()
    return step in FINAL_STEPS or _has_final_dataframe()


def _inject_compact_sidebar_style() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] div[data-testid="stExpander"] details {
            border-radius: 10px !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="stVerticalBlock"] {
            gap: .35rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label {
            font-size: .78rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            font-size: .74rem !important;
            line-height: 1.25rem !important;
        }
        section[data-testid="stSidebar"] hr {
            margin: .35rem 0 .55rem 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_final_status_summary() -> None:
    st.caption('✅ CSV final em modo de conferência')
    st.caption('Separador `;` · UTF-8-SIG · imagens por `|` · GTIN inválido limpo')


def render_rules_panel() -> None:
    """Orquestra Regras e Recursos do CSV final.

    BLINGFIX:
    - não renderiza este painel em etapas iniciais;
    - remove abas que davam sensação de conteúdo vazio na sidebar;
    - usa seletor compacto e sempre entrega conteúdo real;
    - mantém regras e recursos em módulos independentes.
    """
    if not _should_render_rules_panel():
        return

    with st.sidebar:
        _inject_compact_sidebar_style()
        with st.expander('Regras e recursos do CSV final', expanded=False):
            _render_final_status_summary()
            st.divider()

            section = st.radio(
                'Área',
                ['Regras', 'Recursos'],
                horizontal=True,
                label_visibility='collapsed',
                key='rules_panel_section_selector',
            )

            if section == 'Recursos':
                render_resources_tab()
            else:
                render_user_rules_tab()
