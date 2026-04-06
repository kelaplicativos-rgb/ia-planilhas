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

    # evita múltiplas execuções simultâneas
    if "crawler_rodando" not in st.session_state:
        st.session_state["crawler_rodando"] = False

    if url:

        if st.button("Buscar produtos do site", width="stretch") and not st.session_state["crawler_rodando"]:

            st.session_state["crawler_rodando"] = True

            log_debug(f"Iniciando crawler: {url}")

            progress = st.progress(0)
            status = st.empty()
            detalhe = st.empty()

            try:
                # ETAPA 1
                status.info("🔎 Conectando ao site...")
                detalhe.write("Abrindo conexão com servidor")
                progress.progress(10)

                # ETAPA 2
                status.info("📦 Coletando páginas...")
                detalhe.write("Mapeando categorias e paginação")
                progress.progress(25)

                # ETAPA 3
                status.info("📄 Extraindo produtos...")
                detalhe.write("Capturando dados do HTML")

                df_origem = executar_crawler(url)

                progress.progress(60)

                if df_origem is None or len(df_origem) == 0:
                    st.error("Nenhum produto encontrado")
                    st.session_state["crawler_rodando"] = False
                    return None

                # ETAPA 4
                status.info("🧠 Processando com IA...")
                detalhe.write("Padronizando estrutura dos dados")

                df_origem = pd.DataFrame(df_origem)

                # 🔥 APLICA ESTOQUE PADRÃO
                if "estoque" not in df_origem.columns:
                    df_origem["estoque"] = estoque_padrao_site
                else:
                    df_origem["estoque"] = df_origem["estoque"].fillna(estoque_padrao_site)

                progress.progress(85)

                # ETAPA 5
                status.info("📊 Finalizando...")
                detalhe.write(f"{len(df_origem)} produtos processados")

                progress.progress(100)
                status.success("✅ Concluído com sucesso")

                st.session_state["df_origem_site"] = df_origem

                log_debug(f"Crawler finalizado: {len(df_origem)} produtos", "SUCCESS")

                st.session_state["crawler_rodando"] = False

                return df_origem

            except Exception as e:
                log_debug(f"Erro crawler: {e}", "ERROR")
                status.error("Erro no processamento")
                detalhe.write(str(e))
                st.error("Erro ao buscar site")

                st.session_state["crawler_rodando"] = False
                return None

    return st.session_state.get("df_origem_site")
