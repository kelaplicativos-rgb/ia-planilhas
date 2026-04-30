from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.instant_scraper.auto_merge import auto_merge_produtos
from bling_app_zero.core.instant_scraper.flow_contract import (
    criar_estado_inicial,
    atualizar_status,
    registrar_html,
    registrar_candidatos,
    registrar_produtos,
)
from bling_app_zero.core.instant_scraper.html_fetcher import fetch_html, limpar_cache_html
from bling_app_zero.core.instant_scraper.instant_dom_engine import instant_candidates_to_frames
from bling_app_zero.core.instant_scraper.sitemap_enricher import varrer_site_por_sitemap
from bling_app_zero.ui.instant_flow_panel import render_instant_flow


ORDEM_PREVIEW_SITE = [
    "produto_id_url",
    "sku",
    "nome",
    "preco",
    "moeda",
    "marca",
    "categoria",
    "gtin",
    "estoque",
    "url_produto",
    "imagens",
    "descricao",
]


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


def _ordenar_preview(df: pd.DataFrame) -> pd.DataFrame:
    if not _df_ok(df):
        return pd.DataFrame()

    base = df.copy().fillna("")
    for col in ORDEM_PREVIEW_SITE:
        if col not in base.columns:
            base[col] = ""

    outras = [c for c in base.columns if c not in ORDEM_PREVIEW_SITE]
    return base[ORDEM_PREVIEW_SITE + outras]


def _limpar_busca_site() -> None:
    for chave in [
        "instant_candidates",
        "instant_html",
        "instant_url",
        "instant_selected_id",
        "sitemap_stats",
        "sitemap_df",
        "visual_df",
        "df_origem",
        "site_resultado_origem",
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


def _aplicar_auto_merge() -> pd.DataFrame:
    df_sitemap = st.session_state.get("sitemap_df")
    df_visual = st.session_state.get("visual_df")

    if _df_ok(df_sitemap) and _df_ok(df_visual):
        merged = auto_merge_produtos(("sitemap", df_sitemap), ("visual", df_visual))
        st.session_state["df_origem"] = _ordenar_preview(merged)
        st.session_state["site_resultado_origem"] = "auto_merge"
        return st.session_state["df_origem"]

    if _df_ok(df_sitemap):
        st.session_state["df_origem"] = _ordenar_preview(df_sitemap)
        st.session_state["site_resultado_origem"] = "sitemap"
        return st.session_state["df_origem"]

    if _df_ok(df_visual):
        st.session_state["df_origem"] = _ordenar_preview(df_visual)
        st.session_state["site_resultado_origem"] = "visual"
        return st.session_state["df_origem"]

    return pd.DataFrame()


def _salvar_df_origem(df: pd.DataFrame, origem: str) -> None:
    base = _ordenar_preview(df)

    if origem == "sitemap":
        st.session_state["sitemap_df"] = base
    elif origem == "visual":
        st.session_state["visual_df"] = base

    final = _aplicar_auto_merge()
    if final.empty:
        final = base
        st.session_state["df_origem"] = final
        st.session_state["site_resultado_origem"] = origem

    state = st.session_state.get("instant_state")
    if state is not None:
        registrar_produtos(state, len(final))
        atualizar_status(state, "concluido")


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


def _varrer_sitemap(url: str, limite_produtos: int) -> None:
    state = _estado_atual(url)
    atualizar_status(state, "extraindo")

    with st.spinner("Varrendo sitemaps e enriquecendo paginas de produto..."):
        df, stats = varrer_site_por_sitemap(
            base_url=url,
            fetcher=lambda u: fetch_html(u, force_refresh=True),
            limite_produtos=limite_produtos,
        )

    st.session_state["sitemap_stats"] = stats
    st.session_state["sitemap_df"] = df

    registrar_candidatos(state, int(getattr(stats, "urls_produto", 0) or 0))

    if not _df_ok(df):
        atualizar_status(state, "erro", "Sitemap Mode nao encontrou produtos uteis.")
        return

    _salvar_df_origem(df, "sitemap")
    st.success(f"Sitemap Mode concluiu com {len(df)} produto(s).")


def _usar_candidato(candidato: dict[str, Any]) -> None:
    df = candidato.get("dataframe")
    if not _df_ok(df):
        st.warning("Esta estrutura nao possui dados uteis.")
        return

    st.session_state["instant_selected_id"] = candidato.get("id")
    _salvar_df_origem(df, "visual")
    st.success(f"Estrutura selecionada com {len(df)} registro(s).")


def _render_sitemap_stats() -> None:
    stats = st.session_state.get("sitemap_stats")
    if not stats:
        return

    st.markdown("### Diagnostico Sitemap Mode")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sitemaps lidos", int(getattr(stats, "sitemap_lidos", 0) or 0))
    c2.metric("URLs no sitemap", int(getattr(stats, "urls_sitemap", 0) or 0))
    c3.metric("URLs produto", int(getattr(stats, "urls_produto", 0) or 0))
    c4.metric("Produtos extraidos", int(getattr(stats, "produtos_extraidos", 0) or 0))
    st.caption(f"Motivo/parada: {getattr(stats, 'motivo', '')}")


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
                st.dataframe(_ordenar_preview(df_preview).head(10), use_container_width=True)
            else:
                st.info("Sem preview disponivel para esta estrutura.")

            if st.button(f"Usar opcao {cid}", key=f"usar_instant_{cid}", use_container_width=True):
                _usar_candidato(candidato)


def _render_resultado_final() -> None:
    df = _aplicar_auto_merge()
    if not _df_ok(df):
        return

    base = _ordenar_preview(df)
    st.session_state["df_origem"] = base

    st.markdown("### Resultado selecionado")
    origem = _txt(st.session_state.get("site_resultado_origem", "")) or "site"

    if origem == "auto_merge":
        st.info(f"Auto merge aplicado: {len(base)} produtos consolidados.")
    else:
        st.caption(f"Origem do resultado: {origem}. Colunas organizadas para mapeamento Bling.")

    st.dataframe(base.head(80), use_container_width=True)

    csv = base.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "Baixar preview CSV",
        data=csv,
        file_name="produtos_busca_site.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_origem_site_panel() -> None:
    st.markdown("#### Busca por site - Sitemap Mode + selecao visual")
    st.caption("Use Sitemap Mode para varrer o site completo ou selecao visual para escolher uma estrutura da pagina atual.")

    url_input = st.text_input(
        "URL do fornecedor, categoria ou dominio",
        value=_txt(st.session_state.get("site_url_input", "")),
        placeholder="Ex.: https://www.megacentereletronicos.com.br",
        key="site_url_input",
    )
    url = _normalizar_url(url_input)

    state = _estado_atual(url)
    render_instant_flow(state)

    limite_produtos = st.number_input(
        "Limite de produtos na varredura completa",
        min_value=20,
        max_value=2000,
        value=500,
        step=20,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Varrer site completo", use_container_width=True, type="primary", disabled=not bool(url)):
            _varrer_sitemap(url, int(limite_produtos))
    with col2:
        if st.button("Detectar estruturas da pagina", use_container_width=True, disabled=not bool(url)):
            _detectar_candidatos(url)
    with col3:
        if st.button("Limpar busca", use_container_width=True):
            _limpar_busca_site()
            st.success("Busca limpa.")

    _render_sitemap_stats()
    _render_candidatos()
    _render_resultado_final()
