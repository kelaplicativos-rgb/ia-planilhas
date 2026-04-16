
from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.ui.ia_panel import render_ia_panel
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.preview_final import render_preview_final

APP_VERSION = "2.3.2"


# ============================================================
# ESTADO BASE
# ============================================================


def _init_state() -> None:
    defaults = {
        "fluxo_etapa": "origem",
        "tipo_operacao": "",
        "tipo_operacao_bling": "",
        "arquivo_origem_nome": "",
        "modelo_cadastro_nome": "",
        "modelo_estoque_nome": "",
        "df_origem": None,
        "df_origem_precificado": None,
        "df_modelo_base": None,
        "df_base_mapeamento": None,
        "df_final": None,
        "mapeamento_colunas": {},
        "campos_pendentes": [],
        "deposito_nome": "",
        "preco_coluna_origem": "",
        "preco_imposto_pct": "",
        "preco_margem_pct": "",
        "preco_custo_fixo": "",
        "preco_taxa_fixa": "",
        "agent_plan": None,
        "agent_outputs": {},
        "url_site_origem": "",
        "ia_prompt_home": "",
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _go(etapa: str) -> None:
    st.session_state["fluxo_etapa"] = etapa
    st.rerun()


# ============================================================
# HELPERS
# ============================================================


def _has_df(value: Any) -> bool:
    try:
        return value is not None and hasattr(value, "empty") and not value.empty
    except Exception:
        return False


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _has_mapping() -> bool:
    mapping = st.session_state.get("mapeamento_colunas")
    return isinstance(mapping, dict) and len(mapping) > 0


def _has_plan() -> bool:
    plan = st.session_state.get("agent_plan")
    return isinstance(plan, dict) and len(plan) > 0


def _can_go_precificacao() -> bool:
    modelo_ok = _has_df(st.session_state.get("df_modelo_base"))
    origem_ok = _has_df(st.session_state.get("df_origem")) or _has_df(st.session_state.get("df_base_mapeamento"))
    site_ok = _has_text(st.session_state.get("url_site_origem"))
    plan_ok = _has_plan()
    return modelo_ok and (origem_ok or site_ok or plan_ok)


def _can_go_mapeamento() -> bool:
    return _has_df(st.session_state.get("df_origem_precificado")) or _has_df(
        st.session_state.get("df_base_mapeamento")
    )


def _can_go_preview() -> bool:
    return _has_df(st.session_state.get("df_final"))


# ============================================================
# ESTILO
# ============================================================


def _render_css() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 860px;
                padding-top: 1rem;
                padding-bottom: 2rem;
            }

            .bx-hero {
                border: 1px solid rgba(20, 22, 28, 0.10);
                border-radius: 22px;
                padding: 20px 18px 18px 18px;
                margin-bottom: 18px;
                background: #ffffff;
            }

            .bx-title {
                font-size: 2.05rem;
                line-height: 1.05;
                font-weight: 800;
                letter-spacing: -0.02em;
                color: #222531;
                margin: 0 0 10px 0;
            }

            .bx-subtitle {
                font-size: 1rem;
                color: #5d6472;
                margin: 0 0 18px 0;
            }

            .bx-pills {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                margin-top: 6px;
            }

            .bx-pill {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 12px 22px;
                border-radius: 999px;
                border: 1px solid #d8dbe3;
                background: #f2f3f7;
                color: #2d3240;
                font-size: 0.95rem;
                font-weight: 700;
            }

            .bx-pill.active {
                background: #0d2e6f;
                color: #ffffff;
                border-color: #0d2e6f;
            }

            div[data-testid="stButton"] > button {
                border-radius: 14px;
                min-height: 48px;
                font-weight: 700;
            }

            div[data-testid="stFileUploader"] section {
                border-radius: 16px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# HEADER
# ============================================================


def _render_header() -> None:
    etapa = st.session_state["fluxo_etapa"]

    mapa = {
        "origem": "1. Origem",
        "precificacao": "2. Precisão",
        "mapeamento": "3. Mapeamento",
        "preview": "4. Pré-visualização",
    }

    pills = []
    for chave, label in mapa.items():
        css = "bx-pill active" if etapa == chave else "bx-pill"
        pills.append(f'<div class="{css}">{label}</div>')

    st.markdown(
        f"""
        <div class="bx-hero">
            <div class="bx-title">IA Planilhas → Bling</div>
            <div class="bx-subtitle">
                Fluxo guiado para origem, precificação, mapeamento e visualização final.
            </div>
            <div class="bx-pills">
                {''.join(pills)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# RENDER DAS ETAPAS
# ============================================================


def _render_etapa_atual() -> None:
    etapa = st.session_state["fluxo_etapa"]

    if etapa == "origem":
        render_ia_panel()
        return

    if etapa == "precificacao":
        render_origem_precificacao()
        return

    if etapa == "mapeamento":
        render_origem_mapeamento()
        return

    render_preview_final()


# ============================================================
# NAVEGAÇÃO
# ============================================================


def _render_footer_nav() -> None:
    etapa = st.session_state["fluxo_etapa"]
    col1, col2 = st.columns(2)

    with col1:
        if etapa == "precificacao":
            if st.button("← Voltar para origem", use_container_width=True):
                _go("origem")

        elif etapa == "mapeamento":
            if st.button("← Voltar para precisão", use_container_width=True):
                _go("precificacao")

        elif etapa == "preview":
            if st.button("← Voltar para mapeamento", use_container_width=True):
                _go("mapeamento")

    with col2:
        if etapa == "origem":
            if st.button(
                "Continuar para precificação →",
                use_container_width=True,
                disabled=not _can_go_precificacao(),
            ):
                _go("precificacao")

        elif etapa == "precificacao":
            if st.button(
                "Continuar para mapeamento →",
                use_container_width=True,
                disabled=not _can_go_mapeamento(),
            ):
                _go("mapeamento")

        elif etapa == "mapeamento":
            if st.button(
                "Continuar para pré-visualização →",
                use_container_width=True,
                disabled=not _can_go_preview(),
            ):
                _go("preview")


# ============================================================
# APP
# ============================================================


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas → Bling",
        layout="centered",
    )

    _init_state()
    _render_css()
    _render_header()
    _render_etapa_atual()
    _render_footer_nav()
    st.caption(f"Versão: {APP_VERSION}")


if __name__ == "__main__":
    main()
    
