from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_crawler import executar_crawler
from bling_app_zero.ui.origem_dados_helpers import log_debug


def render_origem_site():
    url = st.text_input("URL do site", key="url_site_origem")

    estoque_padrao_site = st.number_input(
        "Estoque padrão quando disponível",
        min_value=0,
        value=10,
        step=1,
        key="estoque_padrao_site",
    )

    if url:

        if st.button("Buscar produtos do site", width="stretch"):

            log_debug(f"Iniciando crawler: {url}")

            progress = st.progress(0)
            status = st.empty()
            detalhe = st.empty()

            try:
                status.info("🔎 Conectando ao site...")
                detalhe.write("Abrindo conexão")
                progress.progress(10)

                status.info("📦 Coletando páginas...")
                detalhe.write("Mapeando estrutura")
                progress.progress(30)

                status.info("📄 Extraindo produtos...")
                detalhe.write("Capturando dados")

                df_origem = executar_crawler(url)

                progress.progress(60)

                if df_origem is None or df_origem.empty:
                    st.error("Nenhum produto encontrado")
                    return None

                status.info("🧠 Processando IA...")
                detalhe.write("Padronizando dados")

                df_origem = pd.DataFrame(df_origem)

                progress.progress(90)

                status.info("📊 Finalizando...")
                detalhe.write(f"{len(df_origem)} produtos")

                progress.progress(100)
                status.success("✅ Concluído")

                st.session_state["df_origem_site"] = df_origem

                return df_origem

            except Exception as e:
                log_debug(f"Erro crawler: {e}", "ERROR")
                status.error("Erro no processamento")
                st.error("Erro ao buscar site")
                return None

    return st.session_state.get("df_origem_site")
