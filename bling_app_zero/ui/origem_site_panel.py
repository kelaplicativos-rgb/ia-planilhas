# (mantive imports originais)

from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.core.site_agent import buscar_produtos_site_com_gpt, SiteAgent
except Exception:
    buscar_produtos_site_com_gpt = None
    SiteAgent = None

from bling_app_zero.ui.app_helpers import log_debug

# =========================
# 🔥 NOVO: BLINDAGEM TOTAL HTTP-FIRST
# =========================

def _forcar_http_first_execucao():
    st.session_state["preferir_http"] = True
    st.session_state["crawler_runtime_mode"] = "http_hybrid"
    st.session_state["crawler_forcar_http"] = True
    st.session_state["crawler_browser_disponivel"] = False
    st.session_state["playwright_habilitado"] = False
    st.session_state["playwright_browser_ok"] = False

    # limpa qualquer sujeira antiga
    for k in [
        "_playwright_bootstrap",
        "site_busca_usa_playwright",
        "site_login_usa_playwright",
    ]:
        st.session_state.pop(k, None)


# =========================
# 🔥 EXECUÇÃO DA BUSCA (CORRIGIDA)
# =========================

def _executar_busca_site(url_site: str) -> None:
    url_site = str(url_site or "").strip()

    if not url_site:
        st.error("Informe a URL do fornecedor ou da categoria.")
        return

    # 🔥 FORÇA NOVO MODO
    _forcar_http_first_execucao()

    log_debug(f"[BUSCA] iniciando em modo HTTP-FIRST: {url_site}")

    st.session_state["site_busca_em_execucao"] = True
    st.session_state["site_busca_ultimo_status"] = "executando"
    st.session_state["site_busca_resumo_texto"] = "Executando busca IA..."

    try:
        # 🔥 PRIORIDADE TOTAL PARA NOVO AGENTE
        if SiteAgent is not None:
            agent = SiteAgent()

            df_site = agent.buscar_dataframe(
                base_url=url_site,
                diagnostico=True,
                auth_context=None,
                limite=500,
            )

        elif buscar_produtos_site_com_gpt is not None:
            df_site = buscar_produtos_site_com_gpt(
                base_url=url_site,
                diagnostico=True,
                limite_links=500,
            )
        else:
            raise RuntimeError("Nenhum mecanismo de busca disponível.")

        # normalização
        if isinstance(df_site, list):
            df_site = pd.DataFrame(df_site)

        if not isinstance(df_site, pd.DataFrame) or df_site.empty:
            st.session_state["site_busca_em_execucao"] = False
            st.warning("Nenhum produto encontrado.")
            return

        df_site = df_site.fillna("")

        # salva no fluxo principal
        st.session_state["df_origem"] = df_site
        st.session_state["origem_upload_tipo"] = "site"

        total = len(df_site)

        st.session_state["site_busca_em_execucao"] = False
        st.session_state["site_busca_ultimo_status"] = "sucesso"
        st.session_state["site_busca_ultimo_total"] = total

        st.success(f"{total} produto(s) encontrados.")

    except Exception as e:
        st.session_state["site_busca_em_execucao"] = False
        st.error(f"Erro na busca: {e}")
        log_debug(f"[ERRO BUSCA SITE] {e}", nivel="ERRO")


# =========================
# 🔥 BOTÕES (SIMPLIFICADO E DIRETO)
# =========================

def _render_bloco_acao(url_site: str):
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Buscar produtos", use_container_width=True):
            _executar_busca_site(url_site)
            st.rerun()

    with col2:
        if st.button("Limpar busca", use_container_width=True):
            st.session_state.pop("df_origem", None)
            st.info("Busca limpa.")
            st.rerun()


# =========================
# 🔥 UI PRINCIPAL
# =========================

def render_origem_site_panel():
    with st.container(border=True):

        st.markdown("### Buscar no site do fornecedor")
        st.caption("Crawler IA ABSURDA PRO (sem navegador)")

        url_site = st.text_input(
            "URL do fornecedor ou categoria",
            placeholder="https://site.com/categoria",
            key="site_url_input",
        )

        _render_bloco_acao(url_site)

        df = st.session_state.get("df_origem")

        if isinstance(df, pd.DataFrame):
            with st.expander("Preview da busca", expanded=False):
                st.dataframe(df.head(50), use_container_width=True)
