# bling_app_zero/ui/origem_site_panel.py

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.instant_scraper.click_selector import (
    extrair_por_opcao_click,
    gerar_opcoes_click_scraper,
)
from bling_app_zero.core.instant_scraper.html_fetcher import (
    fetch_html,
    obter_ultimo_fetch_info,
    limpar_cache_html,
)
from bling_app_zero.core.instant_scraper.learning_store import (
    limpar_aprendizado,
    obter_aprendizado,
    salvar_aprendizado,
)
from bling_app_zero.core.instant_scraper.runner import run_scraper


def _txt(v: Any) -> str:
    return str(v or "").strip()


def _normalizar_url(url: str) -> str:
    url = _txt(url)
    if not url:
        return ""

    if url.startswith("//"):
        url = "https:" + url

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def _df_ok(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty


def _limpar_estado_busca_site() -> None:
    for chave in [
        "click_html",
        "click_url",
        "click_opcoes",
        "site_busca_status",
        "site_busca_total",
        "site_busca_erro",
    ]:
        st.session_state.pop(chave, None)

    limpar_cache_html()


def _registrar_df(df: pd.DataFrame, url: str) -> None:
    base = df.copy().fillna("")

    st.session_state["df_origem"] = base
    st.session_state["site_url_origem"] = url
    st.session_state["site_busca_status"] = "concluido"
    st.session_state["site_busca_total"] = len(base)
    st.session_state["site_busca_erro"] = ""


def _registrar_erro(msg: str) -> None:
    st.session_state["site_busca_status"] = "erro"
    st.session_state["site_busca_erro"] = msg


def _render_diagnostico_fetch() -> None:
    info = obter_ultimo_fetch_info()

    if not info or not info.get("url"):
        return

    with st.expander("🔍 Diagnóstico da busca", expanded=False):
        st.write(f"URL final: {info.get('url_final')}")
        st.write(f"Status HTTP: {info.get('status_code')}")
        st.write(f"Tipo conteúdo: {info.get('content_type')}")
        st.write(f"Tamanho HTML: {info.get('html_chars')}")
        st.write(f"Cache: {info.get('cache')}")

        if info.get("parece_bloqueio"):
            st.warning("Possível bloqueio anti-bot detectado.")

        if info.get("parece_javascript"):
            st.warning("Este site pode depender de JavaScript (HTTP puro pode não funcionar).")

        if info.get("erro"):
            st.error(info.get("erro"))


def _buscar_html_com_feedback(url: str) -> str:
    barra = st.progress(0)
    status = st.empty()

    try:
        status.info("Conectando ao site...")
        barra.progress(20)

        html = fetch_html(url, force_refresh=True)

        barra.progress(70)
        status.info("Página carregada. Analisando HTML...")

        if not _txt(html):
            barra.progress(100)
            status.error("O site não retornou HTML útil.")
            _render_diagnostico_fetch()
            return ""

        barra.progress(100)
        status.success("HTML carregado com sucesso.")
        _render_diagnostico_fetch()
        return html

    except Exception as exc:
        barra.progress(100)
        status.error(f"Falha ao carregar o site: {exc}")
        return ""


def _detectar_estruturas(url: str) -> None:
    if not url:
        st.error("Informe uma URL válida.")
        return

    st.session_state["site_busca_status"] = "detectando"
    st.session_state["site_busca_erro"] = ""

    html = _buscar_html_com_feedback(url)

    if not html:
        _registrar_erro("Não foi possível carregar HTML útil da URL informada.")
        return

    barra = st.progress(0)
    status = st.empty()

    try:
        status.info("Detectando estruturas semelhantes a produtos...")
        barra.progress(40)

        opcoes = gerar_opcoes_click_scraper(html, url)

        barra.progress(85)

        if not opcoes:
            barra.progress(100)
            _registrar_erro("Nenhuma estrutura detectada.")
            st.error("Nenhuma estrutura detectada.")
            return

        st.session_state["click_html"] = html
        st.session_state["click_url"] = url
        st.session_state["click_opcoes"] = opcoes
        st.session_state["site_busca_status"] = "estruturas_detectadas"
        st.session_state["site_busca_total"] = len(opcoes)

        barra.progress(100)
        status.success(f"{len(opcoes)} estrutura(s) detectada(s).")

    except Exception as exc:
        barra.progress(100)
        _registrar_erro(f"Erro ao detectar estruturas: {exc}")
        st.error(f"Erro ao detectar estruturas: {exc}")

# restante do arquivo permanece igual (sem alterações estruturais)

