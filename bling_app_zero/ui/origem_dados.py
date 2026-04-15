
from __future__ import annotations

import streamlit as st
import pandas as pd

from bling_app_zero.ui.app_helpers import log_debug


# =========================================================
# HELPERS
# =========================================================
def _set_etapa(etapa: str):
    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def _card_button(label, key, active=False):
    if active:
        return st.button(f"🔥 {label}", key=key, use_container_width=True)
    return st.button(label, key=key, use_container_width=True)


# =========================================================
# MAIN
# =========================================================
def render_origem_dados():

    st.markdown("## Começo")

    # =====================================================
    # ETAPA 1 — OPERAÇÃO
    # =====================================================
    st.markdown("### O que você quer fazer?")

    col1, col2 = st.columns(2)

    with col1:
        if _card_button("📦 Cadastro de Produtos", "btn_cadastro"):
            st.session_state["tipo_operacao"] = "cadastro"
            st.rerun()

    with col2:
        if _card_button("📊 Atualização de Estoque", "btn_estoque"):
            st.session_state["tipo_operacao"] = "estoque"
            st.rerun()

    # 🚫 BLOQUEIA resto se não escolheu
    if "tipo_operacao" not in st.session_state:
        return

    st.divider()

    # =====================================================
    # ETAPA 2 — ORIGEM
    # =====================================================
    st.markdown("### De onde virão os dados?")

    col1, col2 = st.columns(2)

    with col1:
        if _card_button("📄 Planilha / CSV / XML", "btn_planilha"):
            st.session_state["origem_tipo"] = "planilha"
            st.rerun()

    with col2:
        if _card_button("🌐 Buscar em site", "btn_site"):
            st.session_state["origem_tipo"] = "site"
            st.rerun()

    # 🚫 BLOQUEIA resto se não escolheu
    if "origem_tipo" not in st.session_state:
        return

    st.divider()

    # =====================================================
    # ETAPA 3 — ENTRADA
    # =====================================================
    if st.session_state["origem_tipo"] == "planilha":

        st.markdown("### Envie sua planilha")

        arquivo = st.file_uploader(
            "Selecione o arquivo",
            type=["xlsx", "xls", "csv", "xml"],
            label_visibility="collapsed",
        )

        if arquivo:
            try:
                if arquivo.name.endswith(".csv"):
                    df = pd.read_csv(arquivo)
                else:
                    df = pd.read_excel(arquivo)

                st.session_state["df_origem"] = df
                log_debug("Arquivo carregado com sucesso")

                st.success(f"{len(df)} linhas carregadas")

                if st.button("Continuar ➜", use_container_width=True):
                    _set_etapa("mapeamento")
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao ler arquivo: {e}")

    else:
        st.markdown("### Informe a URL")

        url = st.text_input(
            "URL do site",
            placeholder="https://...",
            label_visibility="collapsed",
        )

        if url:
            st.session_state["site_url"] = url

            if st.button("Continuar ➜", use_container_width=True):
                _set_etapa("mapeamento")
                st.rerun()

    # =====================================================
    # VOLTAR (RESET LIMPO)
    # =====================================================
    st.divider()

    if st.button("⬅️ Voltar", use_container_width=True):
        for k in ["tipo_operacao", "origem_tipo", "df_origem"]:
            st.session_state.pop(k, None)
        st.rerun()
        
