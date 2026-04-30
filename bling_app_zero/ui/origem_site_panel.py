from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.instant_scraper.flow_contract import (
    criar_estado_inicial,
    atualizar_status,
    registrar_html,
    registrar_candidatos,
    registrar_produtos,
)
from bling_app_zero.core.instant_scraper.html_fetcher import fetch_html, limpar_cache_html
from bling_app_zero.core.instant_scraper.instant_dom_engine import instant_candidates_to_frames
from bling_app_zero.ui.instant_flow_panel import render_instant_flow


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


def _limpar_busca_site() -> None:
    for chave in [
        "instant_candidates",
        "instant_html",
        "instant_url",
        "instant_selected_id",
        "df_origem",
    ]:
        st.session_state.pop(chave, None)
    try:
        limpar_cache_html()
    except Exception:
        pass


def _estado_atual(url: str):
    if "instant_state" not in st.session_state:
        st.session_state["instant_state"] = criar_estado_inicial(url)
    state = st.session_state["instant_state"]
    state.url = url
    state.modo_runtime = str(st.session_state.get("site_runtime_modo", "http_dom"))
    state.browser_disponivel = bool(st.session_state.get("site_runtime_browser_opcional", False))
    return state


def _detectar_candidatos(url: str) -> None:
    state = _estado_atual(url)
    atualizar_status(state, "carregando_html")

    html = fetch_html(url, force_refresh=True)
    registrar_html(state, html)

    if not _txt(html):
        atualizar_status(state, "erro", "O site nao retornou HTML util.")
        return

    atualizar_status(state, "detectando_estruturas")
    candidatos = instant_candidates_to_frames(html, url, min_score=30, limit=8)

    st.session_state["instant_html"] = html
    st.session_state["instant_url"] = url
    st.session_state["instant_candidates"] = candidatos

    registrar_candidatos(state, len(candidatos))

    if not candidatos:
        atualizar_status(state, "erro", "Nenhuma estrutura util foi detectada.")
        return

    atualizar_status(state, "estruturas_detectadas")


def _usar_candidato(candidato: dict[str, Any]) -> None:
    df = candidato.get("dataframe")
    if not _df_ok(df):
        st.warning("Esta estrutura nao possui dados uteis.")
        return

    st.session_state["df_origem"] = df.copy().fillna("")
    st.session_state["instant_selected_id"] = candidato.get("id")

    state = st.session_state.get("instant_state")
    if state is not None:
        registrar_produtos(state, len(df))
        atualizar_status(state, "concluido")

    st.success(f"Estrutura selecionada com {len(df)} registro(s).")


def _render_candidatos() -> None:
    candidatos = st.session_state.get("instant_candidates", [])
    if not candidatos:
        return

    st.markdown("### Estruturas detectadas")
    st.caption("Confira o preview e escolha a estrutura que representa melhor os produtos.")

    for candidato in candidatos:
        cid = candidato.get("id")
        score = candidato.get("score", 0)
        kind = candidato.get("kind", "")
        selector = candidato.get("selector", "")
        total_rows = candidato.get("total_rows", 0)
        df_preview = candidato.get("dataframe")

        with st.container(border=True):
            st.markdown(f"#### Opcao {cid} - Score {score} - Tipo {kind}")
            st.caption(f"Linhas detectadas: {total_rows} | Assinatura: {selector}")

            if _df_ok(df_preview):
                st.dataframe(df_preview.head(10), use_container_width=True)
            else:
                st.info("Sem preview disponivel para esta estrutura.")

            if st.button(f"Usar opcao {cid}", key=f"usar_instant_{cid}", use_container_width=True):
                _usar_candidato(candidato)


def _render_resultado_final() -> None:
    df = st.session_state.get("df_origem")
    if not _df_ok(df):
        return

    st.markdown("### Resultado selecionado")
    st.dataframe(df.head(50), use_container_width=True)

    csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "Baixar preview CSV",
        data=csv,
        file_name="produtos_busca_site.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_origem_site_panel() -> None:
    st.markdown("#### Busca por site - selecao visual")
    st.caption("Fluxo estilo extensao: detecta estruturas, mostra previews e voce escolhe a melhor.")

    url_input = st.text_input(
        "URL do fornecedor ou categoria",
        value=_txt(st.session_state.get("site_url_input", "")),
        placeholder="Ex.: https://www.megacentereletronicos.com.br",
        key="site_url_input",
    )
    url = _normalizar_url(url_input)

    state = _estado_atual(url)
    render_instant_flow(state)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Detectar estruturas", use_container_width=True, type="primary", disabled=not bool(url)):
            _detectar_candidatos(url)
    with col2:
        if st.button("Limpar busca", use_container_width=True):
            _limpar_busca_site()
            st.success("Busca limpa.")

    _render_candidatos()
    _render_resultado_final()
