
from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.ia_panel import render_ia_panel
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final

APP_VERSION = "2.3.1"


# ============================================================
# ESTADO
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


# ============================================================
# VALIDADORES
# ============================================================


def _tem_df(valor: object) -> bool:
    try:
        return valor is not None and hasattr(valor, "empty") and not valor.empty
    except Exception:
        return False


def _pode_ir_precificacao() -> bool:
    return _tem_df(st.session_state.get("df_origem")) and _tem_df(st.session_state.get("df_modelo_base"))


def _pode_ir_mapeamento() -> bool:
    return _tem_df(st.session_state.get("df_origem_precificado"))


def _pode_ir_preview() -> bool:
    return _tem_df(st.session_state.get("df_final"))


# ============================================================
# UI BASE
# ============================================================


def _render_css() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 1rem;
                padding-bottom: 2rem;
                max-width: 820px;
            }

            .bx-hero {
                border: 1px solid rgba(20, 22, 28, 0.10);
                border-radius: 22px;
                padding: 20px 18px 18px 18px;
                margin-bottom: 18px;
                background: #ffffff;
            }

            .bx-title {
                font-size: 2.10rem;
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

            .bx-section-title {
                font-size: 1.05rem;
                font-weight: 800;
                color: #232633;
                margin: 0 0 4px 0;
            }

            .bx-section-desc {
                color: #707786;
                font-size: 0.94rem;
                margin: 0 0 12px 0;
            }

            .bx-home-hint {
                border: 1px solid rgba(20, 22, 28, 0.10);
                border-radius: 18px;
                padding: 14px 14px 12px 14px;
                margin: 8px 0 16px 0;
                background: #fbfbfd;
            }

            div[data-testid="stButton"] > button {
                border-radius: 14px;
                min-height: 48px;
                font-weight: 700;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
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
        pills.append(f'<div class="{css}">{label}</div>')

    st.markdown(
        f"""
        <div class="bx-hero">
            <div class="bx-title">IA Planilhas → Bling</div>
            <div class="bx-subtitle">
                Fluxo guiado para origem, precificação, mapeamento e preview final.
            </div>
            <div class="bx-pills">
                {''.join(pills)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_home_hint() -> None:
    st.markdown(
        """
        <div class="bx-home-hint">
            <div class="bx-section-title">Origem dos dados</div>
            <div class="bx-section-desc">
                Aqui precisa aparecer o painel da IA para interpretar o pedido,
                receber a planilha fornecedora, o modelo do Bling e preparar o mapeamento.
            </div>
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
            pode = _pode_ir_precificacao()
            if st.button(
                "Continuar para precificação →",
                use_container_width=True,
                disabled=not pode,
            ):
                _go("precificacao")

        elif etapa == "precificacao":
            pode = _pode_ir_mapeamento()
            if st.button(
                "Continuar para mapeamento →",
                use_container_width=True,
                disabled=not pode,
            ):
                _go("mapeamento")

        elif etapa == "mapeamento":
            pode = _pode_ir_preview()
            if st.button(
                "Continuar para preview →",
                use_container_width=True,
                disabled=not pode,
            ):
                _go("preview")


# ============================================================
# RENDER PRINCIPAL
# ============================================================


def _render_current_step() -> None:
    etapa = st.session_state["fluxo_etapa"]

    if etapa == "origem":
        _render_home_hint()
        render_ia_panel()
        return

    if etapa == "precificacao":
        render_origem_precificacao()
        return

    if etapa == "mapeamento":
        render_origem_mapeamento()
        return

    render_preview_final()


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas → Bling",
        layout="centered",
    )

    _init_state()
    _render_css()
    _render_header()
    _render_current_step()
    _render_footer_nav()
    st.caption(f"Versão: {APP_VERSION}")


if __name__ == "__main__":
    main()


