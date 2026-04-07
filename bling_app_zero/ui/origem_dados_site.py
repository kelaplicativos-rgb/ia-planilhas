from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import log_debug


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _obter_executar_crawler():
    try:
        from bling_app_zero.core.site_crawler import executar_crawler
        return executar_crawler
    except Exception as e:
        log_debug(f"Falha ao importar crawler: {e}", "ERROR")
        return None


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

    def ajustar(valor):
        texto = str(valor or "").strip().lower()

        if texto in {"", "nan", "none", "null"}:
            return int(estoque_padrao_site)

        if any(token in texto for token in [
            "esgotado", "indispon", "sem estoque", "out of stock"
        ]):
            return 0

        try:
            return int(float(texto.replace(",", ".")))
        except Exception:
            return int(estoque_padrao_site)

    df_saida[coluna_estoque] = df_saida[coluna_estoque].apply(ajustar)
    return df_saida


def render_origem_site():
    st.markdown("### 🌐 Captação de produtos via site")

    url = st.text_input("URL do site", key="url_site_origem")

    estoque_padrao_site = st.number_input(
        "Estoque padrão quando disponível",
        min_value=0,
        value=10,
        step=1,
        key="estoque_padrao_site",
    )

    # =========================
    # ESTADO CONTROLADO
    # =========================
    if "crawler_rodando" not in st.session_state:
        st.session_state["crawler_rodando"] = False

    if "df_origem_site" not in st.session_state:
        st.session_state["df_origem_site"] = None

    if "site_processado" not in st.session_state:
        st.session_state["site_processado"] = False

    url_limpa = str(url or "").strip()

    # =========================
    # BOTÃO
    # =========================
    buscar = st.button(
        "🚀 Buscar produtos do site",
        use_container_width=True,
        disabled=st.session_state["crawler_rodando"] or not bool(url_limpa),
    )

    # =========================
    # EXECUÇÃO DO CRAWLER
    # =========================
    if buscar:
        st.session_state["crawler_rodando"] = True
        st.session_state["site_processado"] = False

        progress = st.progress(0)
        status = st.empty()

        try:
            executar_crawler = _obter_executar_crawler()
            if executar_crawler is None:
                st.error("Erro ao carregar o crawler.")
                return None

            status.info("🔎 Conectando ao site...")
            progress.progress(20)

            df_origem = executar_crawler(url_limpa)
            progress.progress(60)

            if df_origem is None or len(df_origem) == 0:
                st.error("Nenhum produto encontrado.")
                st.session_state["df_origem_site"] = None
                return None

            df_origem = pd.DataFrame(df_origem)
            df_origem = _normalizar_coluna_estoque(
                df_origem,
                int(estoque_padrao_site),
            )

            progress.progress(100)

            st.session_state["df_origem_site"] = df_origem.copy()
            st.session_state["site_processado"] = True

            status.success(f"✅ {len(df_origem)} produtos carregados")

            log_debug(f"Crawler finalizado: {len(df_origem)} produtos", "SUCCESS")

        except Exception as e:
            st.error("Erro ao buscar site.")
            log_debug(f"Erro crawler: {e}", "ERROR")
            st.session_state["df_origem_site"] = None

        finally:
            st.session_state["crawler_rodando"] = False

    # =========================
    # PREVIEW
    # =========================
    df_site = st.session_state.get("df_origem_site")

    if _safe_df(df_site):
        with st.expander("📊 Prévia dos dados do site", expanded=False):
            st.dataframe(df_site.head(20), use_container_width=True)

        return df_site.copy()

    return None
