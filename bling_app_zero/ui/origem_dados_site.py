from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_crawler import executar_crawler
from bling_app_zero.ui.origem_dados_helpers import log_debug


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_coluna_estoque(df: pd.DataFrame, estoque_padrao_site: int) -> pd.DataFrame:
    df_saida = df.copy()

    coluna_estoque = None
    for col in df_saida.columns:
        nome = str(col).strip().lower()
        if nome in {"estoque", "saldo", "quantidade", "qtd", "stock"}:
            coluna_estoque = col
            break

    if coluna_estoque is None:
        df_saida["estoque"] = int(estoque_padrao_site)
        return df_saida

    serie = df_saida[coluna_estoque]

    def ajustar(valor):
        if valor is None:
            return int(estoque_padrao_site)

        texto = str(valor).strip().lower()

        if texto in {"", "nan", "none", "null"}:
            return int(estoque_padrao_site)

        if any(token in texto for token in ["esgotado", "indispon", "sem estoque", "out of stock"]):
            return 0

        try:
            return int(float(str(valor).replace(",", ".")))
        except Exception:
            return int(estoque_padrao_site)

    df_saida[coluna_estoque] = serie.apply(ajustar)
    return df_saida


def render_origem_site():
    url = st.text_input("URL do site", key="url_site_origem")

    estoque_padrao_site = st.number_input(
        "Estoque padrão quando disponível",
        min_value=0,
        value=10,
        step=1,
        key="estoque_padrao_site",
    )

    if "crawler_rodando" not in st.session_state:
        st.session_state["crawler_rodando"] = False

    if "df_origem_site" not in st.session_state:
        st.session_state["df_origem_site"] = None

    if "url_site_origem_anterior" not in st.session_state:
        st.session_state["url_site_origem_anterior"] = ""

    url_limpa = str(url or "").strip()

    if url_limpa and st.session_state["url_site_origem_anterior"] != url_limpa:
        st.session_state["df_origem_site"] = None
        st.session_state["url_site_origem_anterior"] = url_limpa

    buscar = st.button(
        "Buscar produtos do site",
        use_container_width=True,
        key="btn_buscar_produtos_site",
        disabled=st.session_state["crawler_rodando"] or not bool(url_limpa),
    )

    if buscar:
        st.session_state["crawler_rodando"] = True
        log_debug(f"Iniciando crawler: {url_limpa}")

        progress = st.progress(0)
        status = st.empty()
        detalhe = st.empty()

        try:
            status.info("🔎 Conectando ao site...")
            detalhe.write("Abrindo conexão com servidor")
            progress.progress(10)

            status.info("📦 Coletando páginas...")
            detalhe.write("Mapeando categorias e paginação")
            progress.progress(25)

            status.info("📄 Extraindo produtos...")
            detalhe.write("Capturando dados do HTML")

            df_origem = executar_crawler(url_limpa)
            progress.progress(60)

            if df_origem is None or len(df_origem) == 0:
                status.error("Nenhum produto encontrado.")
                st.error("Nenhum produto encontrado.")
                st.session_state["crawler_rodando"] = False
                st.session_state["df_origem_site"] = None
                return None

            status.info("🧠 Processando com IA...")
            detalhe.write("Padronizando estrutura dos dados")

            df_origem = pd.DataFrame(df_origem)
            df_origem = _normalizar_coluna_estoque(df_origem, int(estoque_padrao_site))

            progress.progress(85)

            status.info("📊 Finalizando...")
            detalhe.write(f"{len(df_origem)} produtos processados")
            progress.progress(100)
            status.success("✅ Concluído com sucesso")

            st.session_state["df_origem_site"] = df_origem.copy()
            log_debug(f"Crawler finalizado: {len(df_origem)} produtos", "SUCCESS")

        except Exception as e:
            log_debug(f"Erro crawler: {e}", "ERROR")
            status.error("Erro no processamento")
            detalhe.write(str(e))
            st.error("Erro ao buscar site.")
            st.session_state["df_origem_site"] = None
        finally:
            st.session_state["crawler_rodando"] = False

    df_site = st.session_state.get("df_origem_site")
    if _safe_df(df_site):
        with st.expander("🌐 Prévia dos dados do site", expanded=False):
            st.dataframe(df_site.head(20), width="stretch")
        return df_site.copy()

    return None
