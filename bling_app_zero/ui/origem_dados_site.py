from __future__ import annotations

import re
from typing import List

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


def _normalizar_coluna_estoque(
    df: pd.DataFrame,
    estoque_padrao_site: int,
) -> pd.DataFrame:
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

        if any(
            token in texto
            for token in [
                "esgotado",
                "indispon",
                "sem estoque",
                "out of stock",
                "zerado",
            ]
        ):
            return 0

        try:
            return int(float(texto.replace(",", ".")))
        except Exception:
            return int(estoque_padrao_site)

    df_saida[coluna_estoque] = df_saida[coluna_estoque].apply(ajustar)
    return df_saida


def _parse_urls(valor: str) -> List[str]:
    try:
        texto = str(valor or "").strip()
        if not texto:
            return []

        partes = re.split(r"[\n;,]+", texto)
        urls = []

        for parte in partes:
            url = str(parte or "").strip()
            if not url:
                continue

            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"

            if url not in urls:
                urls.append(url)

        return urls
    except Exception:
        return []


def _deduplicar_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df_saida = df.copy()

        for coluna in ["Link Externo", "url", "URL", "link", "Link"]:
            if coluna in df_saida.columns:
                df_saida[coluna] = df_saida[coluna].astype(str).str.strip()
                df_saida = df_saida.drop_duplicates(subset=[coluna])
                return df_saida.reset_index(drop=True)

        return df_saida.drop_duplicates().reset_index(drop=True)
    except Exception:
        return df.reset_index(drop=True)


def render_origem_site():
    st.markdown("### Captação de produtos via site")

    urls_input = st.text_area(
        "URLs do site",
        key="urls_site_origem",
        height=140,
        placeholder=(
            "Cole uma ou várias URLs, uma por linha.\n"
            "Exemplo:\n"
            "https://site.com/categoria/x\n"
            "https://site.com/categoria/y"
        ),
    )

    estoque_padrao_site = st.number_input(
        "Estoque padrão quando disponível",
        min_value=0,
        value=int(st.session_state.get("estoque_padrao_site", 10) or 10),
        step=1,
        key="estoque_padrao_site",
    )

    if "crawler_rodando" not in st.session_state:
        st.session_state["crawler_rodando"] = False

    if "df_origem_site" not in st.session_state:
        st.session_state["df_origem_site"] = None

    if "site_processado" not in st.session_state:
        st.session_state["site_processado"] = False

    urls = _parse_urls(urls_input)

    if urls:
        st.caption(f"{len(urls)} URL(s) detectada(s) para processamento.")

    buscar = st.button(
        "Buscar produtos do site",
        use_container_width=True,
        disabled=st.session_state["crawler_rodando"] or not bool(urls),
        key="botao_buscar_produtos_site",
    )

    if buscar:
        st.session_state["crawler_rodando"] = True
        st.session_state["site_processado"] = False
        st.session_state["df_origem_site"] = None

        progress = st.progress(0)
        status = st.empty()
        detalhe = st.empty()

        try:
            executar_crawler = _obter_executar_crawler()
            if executar_crawler is None:
                st.error("Erro ao carregar o crawler.")
                return None

            total_urls = max(len(urls), 1)
            dfs_resultado: list[pd.DataFrame] = []

            for indice, url_limpa in enumerate(urls, start=1):
                detalhe.info(f"Processando URL {indice}/{total_urls}")
                status.info(f"Conectando ao site: {url_limpa}")

                progresso_base = int(((indice - 1) / total_urls) * 100)
                progress.progress(min(95, max(1, progresso_base + 5)))

                try:
                    df_origem = executar_crawler(
                        url=url_limpa,
                        padrao_disponivel=int(estoque_padrao_site),
                    )

                    if df_origem is None or len(df_origem) == 0:
                        log_debug(
                            f"[SITE] Nenhum produto encontrado na URL: {url_limpa}",
                            "WARNING",
                        )
                        continue

                    df_origem = pd.DataFrame(df_origem)
                    df_origem = _normalizar_coluna_estoque(
                        df_origem,
                        int(estoque_padrao_site),
                    )
                    dfs_resultado.append(df_origem)

                except Exception as e:
                    log_debug(f"[SITE] Erro ao processar URL {url_limpa}: {e}", "ERROR")

                progresso_url = int((indice / total_urls) * 100)
                progress.progress(min(95, max(5, progresso_url)))

            if not dfs_resultado:
                st.error("Nenhum produto encontrado nas URLs informadas.")
                st.session_state["df_origem_site"] = None
                return None

            df_final = pd.concat(dfs_resultado, ignore_index=True)
            df_final = _deduplicar_df(df_final)
            df_final = _normalizar_coluna_estoque(
                df_final,
                int(estoque_padrao_site),
            )

            st.session_state["df_origem_site"] = df_final.copy()
            st.session_state["site_processado"] = True

            progress.progress(100)
            detalhe.empty()
            status.success(f"✅ {len(df_final)} produtos carregados")
            log_debug(
                f"Crawler finalizado com {len(df_final)} produtos em {len(urls)} URL(s)",
                "SUCCESS",
            )

        except Exception as e:
            st.error("Erro ao buscar site.")
            log_debug(f"Erro crawler: {e}", "ERROR")
            st.session_state["df_origem_site"] = None

        finally:
            st.session_state["crawler_rodando"] = False

    df_site = st.session_state.get("df_origem_site")

    if _safe_df(df_site):
        with st.expander("Prévia dos dados do site", expanded=False):
            st.dataframe(df_site.head(20), use_container_width=True, hide_index=True)

        return df_site.copy()

    return None
