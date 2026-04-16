
from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.ia_panel import render_ia_panel
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final

APP_VERSION = "2.3.0"


def _init_state() -> None:
    defaults = {
        "fluxo_etapa": "origem",
        "tipo_operacao": "",
        "arquivo_origem_nome": "",
        "modelo_cadastro_nome": "",
        "modelo_estoque_nome": "",
        "df_origem": None,
        "df_origem_precificado": None,
        "df_modelo_base": None,
        "df_final": None,
        "mapeamento_colunas": {},
        "campos_pendentes": [],
        "deposito_nome": "",
        "preco_coluna_origem": "",
        "preco_imposto_pct": "",
        "preco_margem_pct": "",
        "preco_custo_fixo": "",
        "preco_taxa_fixa": "",
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _go(etapa: str) -> None:
    st.session_state["fluxo_etapa"] = etapa
    st.rerun()


def _render_header() -> None:
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 2rem;
            max-width: 820px;
        }
        .bx-card {
            border: 1px solid rgba(49,51,63,.12);
            border-radius: 22px;
            padding: 16px 16px 10px 16px;
            margin-bottom: 14px;
            background: #ffffff;
        }
        .bx-title {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 6px;
        }
        .bx-sub {
            color: #5f6470;
            font-size: .95rem;
            margin-bottom: 0;
        }
        .bx-stepbar {
            display: flex;
            gap: 8px;
            margin: 12px 0 18px 0;
            flex-wrap: wrap;
        }
        .bx-pill {
            border-radius: 999px;
            padding: 8px 12px;
            font-size: .88rem;
            font-weight: 700;
            border: 1px solid rgba(49,51,63,.14);
            background: #f4f6fb;
        }
        .bx-pill.active {
            background: #0a2a66;
            color: white;
            border-color: #0a2a66;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    etapa = st.session_state["fluxo_etapa"]
    mapa = {
        "origem": "1. Origem",
        "precificacao": "2. Precificação",
        "mapeamento": "3. Mapeamento",
        "preview": "4. Preview",
    }

    pills = []
    for chave, label in mapa.items():
        css = "bx-pill active" if etapa == chave else "bx-pill"
        pills.append(f"<div class='{css}'>{label}</div>")

    st.markdown(
        f"""
        <div class="bx-card">
            <div class="bx-title">IA Planilhas → Bling</div>
            <p class="bx-sub">Fluxo guiado para origem, precificação, mapeamento e preview final.</p>
            <div class="bx-stepbar">{''.join(pills)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_footer_nav() -> None:
    etapa = st.session_state["fluxo_etapa"]

    col1, col2 = st.columns(2)

    with col1:
        if etapa == "precificacao":
            if st.button("← Voltar para origem", use_container_width=True):
                _go("origem")
        elif etapa == "mapeamento":
            if st.button("← Voltar para precificação", use_container_width=True):
                _go("precificacao")
        elif etapa == "preview":
            if st.button("← Voltar para mapeamento", use_container_width=True):
                _go("mapeamento")

    with col2:
        if etapa == "origem":
            pode = st.session_state.get("df_origem") is not None and st.session_state.get("df_modelo_base") is not None
            if st.button("Continuar para precificação →", use_container_width=True, disabled=not pode):
                _go("precificacao")
        elif etapa == "precificacao":
            pode = st.session_state.get("df_origem_precificado") is not None
            if st.button("Continuar para mapeamento →", use_container_width=True, disabled=not pode):
                _go("mapeamento")
        elif etapa == "mapeamento":
            pode = st.session_state.get("df_final") is not None
            if st.button("Continuar para preview →", use_container_width=True, disabled=not pode):
                _go("preview")


_init_state()
st.set_page_config(page_title="IA Planilhas → Bling", layout="centered")
_render_header()

etapa = st.session_state["fluxo_etapa"]

if etapa == "origem":
    render_ia_panel()
elif etapa == "precificacao":
    render_origem_precificacao()
elif etapa == "mapeamento":
    render_origem_mapeamento()
else:
    render_preview_final()

_render_footer_nav()

st.caption(f"Versão: {APP_VERSION}")


