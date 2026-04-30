from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_crawler import CrawlConfig, crawl_site
from bling_app_zero.core.instant_scraper import run_scraper as run_autonomous_scraper
from bling_app_zero.ui.app_helpers import log_debug, normalizar_imagens_pipe


@dataclass(frozen=True)
class ScraperPreset:
    nome: str
    descricao: str
    max_urls: int
    max_products: int
    max_depth: int
    timeout: int
    sleep_seconds: float


PRESETS: dict[str, ScraperPreset] = {
    "Seguro": ScraperPreset(
        nome="Seguro",
        descricao="Agente autônomo + fallback seguro. Melhor para Streamlit Cloud e sites sensíveis.",
        max_urls=180,
        max_products=250,
        max_depth=2,
        timeout=15,
        sleep_seconds=0.12,
    ),
    "Rápido": ScraperPreset(
        nome="Rápido",
        descricao="Busca enxuta para testar uma categoria ou poucas URLs.",
        max_urls=80,
        max_products=120,
        max_depth=1,
        timeout=10,
        sleep_seconds=0.05,
    ),
    "Profundo": ScraperPreset(
        nome="Profundo",
        descricao="Varredura maior para categorias extensas. Use quando precisar capturar mais produtos.",
        max_urls=450,
        max_products=700,
        max_depth=3,
        timeout=18,
        sleep_seconds=0.10,
    ),
}


COLUNAS_PRIORITARIAS = [
    "URL",
    "url_produto",
    "Código",
    "codigo",
    "SKU",
    "sku",
    "Descrição",
    "descricao",
    "nome",
    "Preço",
    "preco",
    "Preço de custo",
    "Estoque",
    "estoque",
    "GTIN",
    "gtin",
    "EAN",
    "NCM",
    "Marca",
    "marca",
    "Categoria",
    "categoria",
    "Imagens",
    "imagem",
    "agente_estrategia",
    "agente_score",
]


CHAVES_LIMPAR_SITE = [
    "df_origem",
    "origem_upload_nome",
    "origem_upload_bytes",
    "origem_upload_tipo",
    "origem_upload_ext",
    "origem_site_url",
    "origem_site_urls",
    "origem_site_total_produtos",
    "origem_site_status",
    "origem_site_ultima_busca",
    "origem_site_config",
]


def _normalizar_url(url: str) -> str:
    valor = str(url or "").strip()
    if not valor:
        return ""
    if not valor.startswith(("http://", "https://")):
        valor = "https://" + valor
    return valor.rstrip("/")


def _url_valida(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _extrair_urls(texto: str) -> list[str]:
    urls: list[str] = []
    vistos: set[str] = set()

    for linha in str(texto or "").replace(",", "\n").replace(";", "\n").splitlines():
        url = _normalizar_url(linha)
        if not url or url in vistos:
            continue
        vistos.add(url)
        urls.append(url)

    return urls


def _normalizar_numero(valor: object) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    texto = texto.replace("R$", "").replace(" ", "").strip()
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    return texto


def _limpar_texto(valor: object) -> str:
    return " ".join(str(valor or "").replace("\x00", " ").split()).strip()


def _normalizar_df_site(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    base.columns = [_limpar_texto(c) for c in base.columns]

    for coluna in base.columns:
        base[coluna] = base[coluna].apply(_limpar_texto)

    for coluna_preco in ["Preço", "preco"]:
        if coluna_preco in base.columns:
            base[coluna_preco] = base[coluna_preco].apply(_normalizar_numero)

    for coluna in base.columns:
        nome = coluna.lower()
        if "imagem" in nome or nome in {"imagens", "url imagem", "url imagens", "image", "img"}:
            base[coluna] = base[coluna].apply(normalizar_imagens_pipe)

    if "URL" in base.columns:
        base = base.drop_duplicates(subset=["URL"], keep="first")
    elif "url_produto" in base.columns:
        base = base.drop_duplicates(subset=["url_produto"], keep="first")
    else:
        base = base.drop_duplicates(keep="first")

    existentes = [c for c in COLUNAS_PRIORITARIAS if c in base.columns]
    restantes = [c for c in base.columns if c not in existentes]
    return base[existentes + restantes].reset_index(drop=True)


def _config_from_preset(preset: ScraperPreset) -> CrawlConfig:
    return CrawlConfig(
        max_urls=int(preset.max_urls),
        max_products=int(preset.max_products),
        max_depth=int(preset.max_depth),
        timeout=int(preset.timeout),
        sleep_seconds=float(preset.sleep_seconds),
    )


def _guardar_resultado_site(df: pd.DataFrame, urls: list[str], preset: ScraperPreset) -> None:
    st.session_state["df_origem"] = df
    st.session_state["origem_upload_nome"] = " | ".join(urls)
    st.session_state["origem_upload_bytes"] = b""
    st.session_state["origem_upload_tipo"] = "site"
    st.session_state["origem_upload_ext"] = "site"
    st.session_state["origem_site_url"] = urls[0] if urls else ""
    st.session_state["site_fornecedor_url"] = urls[0] if urls else ""
    st.session_state["origem_site_urls"] = urls
    st.session_state["origem_site_total_produtos"] = int(len(df))
    st.session_state["origem_site_ultima_busca"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.session_state["origem_site_config"] = {
        "preset": preset.nome,
        "max_urls": preset.max_urls,
        "max_products": preset.max_products,
        "max_depth": preset.max_depth,
        "motor": "autonomous_agent_plus_fallback",
    }


def _limpar_busca_site() -> None:
    for chave in CHAVES_LIMPAR_SITE + ["site_fornecedor_url"]:
        st.session_state.pop(chave, None)
    log_debug("Resultado da busca por site limpo pelo usuário.", nivel="INFO")


def _render_cards_status(df: pd.DataFrame) -> None:
    total = int(len(df)) if isinstance(df, pd.DataFrame) else 0
    col_preco = "Preço" if "Preço" in df.columns else "preco" if isinstance(df, pd.DataFrame) and "preco" in df.columns else ""
    col_img = "Imagens" if "Imagens" in df.columns else "imagem" if isinstance(df, pd.DataFrame) and "imagem" in df.columns else ""
    col_estoque = "Estoque" if "Estoque" in df.columns else "estoque" if isinstance(df, pd.DataFrame) and "estoque" in df.columns else ""

    com_preco = int(df[col_preco].astype(str).str.strip().ne("").sum()) if total and col_preco else 0
    com_img = int(df[col_img].astype(str).str.strip().ne("").sum()) if total and col_img else 0
    estoque_zero = int(df[col_estoque].astype(str).str.strip().eq("0").sum()) if total and col_estoque else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Produtos", total)
    c2.metric("Com preço", com_preco)
    c3.metric("Com imagem", com_img)
    c4.metric("Sem estoque", estoque_zero)


def _render_preview_existente() -> None:
    df = st.session_state.get("df_origem")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return
    if str(st.session_state.get("origem_upload_tipo", "") or "") != "site":
        return

    st.success(f"Resultado carregado: {len(df)} produto(s) prontos para o próximo passo.")
    _render_cards_status(df)

    with st.expander("👁️ Preview da captura", expanded=True):
        st.dataframe(df.head(80), use_container_width=True)

    csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "📥 Baixar CSV da captura do site",
        data=csv,
        file_name="captura_site_fornecedor.csv",
        mime="text/csv",
        use_container_width=True,
        key="download_captura_site_csv",
    )


def _render_configuracao() -> tuple[list[str], ScraperPreset]:
    st.markdown("#### 🚀 Captura por site — Agente Autônomo")
    st.caption("Cole uma URL de produto, categoria ou várias URLs em linhas separadas. O agente escolhe a melhor estratégia e usa crawler como fallback.")

    texto_inicial = "\n".join(st.session_state.get("origem_site_urls", [])) or str(st.session_state.get("origem_site_url", "") or "")
    urls_texto = st.text_area(
        "URLs para varrer",
        value=texto_inicial,
        height=110,
        key="origem_site_urls_textarea",
        placeholder="https://site.com/categoria\nhttps://site.com/produto/exemplo",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        preset_nome = st.selectbox(
            "Modo de fallback",
            options=list(PRESETS.keys()),
            index=0,
            key="origem_site_preset",
        )
    with c2:
        st.caption("Configuração")
        st.info(PRESETS[preset_nome].descricao)

    return _extrair_urls(urls_texto), PRESETS[preset_nome]


def _executar_busca(urls: list[str], preset: ScraperPreset) -> pd.DataFrame:
    progress = st.progress(0)
    status = st.empty()
    detalhes = st.empty()
    encontrados_box = st.empty()

    resultados: list[pd.DataFrame] = []
    total_urls = max(len(urls), 1)

    for idx, url in enumerate(urls, start=1):
        base_percent = int(((idx - 1) / total_urls) * 100)
        status.info(f"Agente autônomo lendo URL {idx}/{len(urls)}: {url}")
        detalhes.caption("Estratégia 1: agente autônomo / Instant Scraper")

        try:
            df_url = run_autonomous_scraper(url)
            df_url = _normalizar_df_site(df_url)
            if not df_url.empty:
                if "URL origem da busca" not in df_url.columns:
                    df_url["URL origem da busca"] = url
                resultados.append(df_url)
                progress.progress(max(0, min(int((idx / total_urls) * 100), 100)))
                encontrados_box.caption(f"Produtos encontrados nesta URL: {len(df_url)}")
                log_debug(f"Agente autônomo capturou {len(df_url)} produto(s) em {url}", nivel="INFO")
                continue
            log_debug(f"Agente autônomo não encontrou produtos em {url}; acionando fallback crawler.", nivel="AVISO")
        except Exception as exc:
            log_debug(f"Falha no agente autônomo em {url}: {exc}; acionando fallback crawler.", nivel="ERRO")

        def _callback(percentual: int, mensagem: str, total: int) -> None:
            parcial = int(base_percent + (max(0, min(int(percentual or 0), 100)) / total_urls))
            progress.progress(max(0, min(parcial, 100)))
            detalhes.caption(str(mensagem or "Buscando produtos via fallback..."))
            encontrados_box.caption(f"Produtos encontrados no fallback: {int(total or 0)}")
            st.session_state["origem_site_status"] = str(mensagem or "")

        try:
            df_url = crawl_site(url, config=_config_from_preset(preset), progress_callback=_callback)
            df_url = _normalizar_df_site(df_url)
            if not df_url.empty:
                if "URL origem da busca" not in df_url.columns:
                    df_url["URL origem da busca"] = url
                if "agente_estrategia" not in df_url.columns:
                    df_url["agente_estrategia"] = "crawler_fallback"
                resultados.append(df_url)
                log_debug(f"Fallback crawler encontrou {len(df_url)} produto(s) em {url}", nivel="INFO")
            else:
                log_debug(f"Fallback crawler não encontrou produtos em {url}", nivel="AVISO")
        except Exception as exc:
            log_debug(f"Falha no fallback crawler em {url}: {exc}", nivel="ERRO")
            st.warning(f"Falha ao buscar em {url}: {exc}")

    progress.progress(100)
    status.success("Busca finalizada.")
    detalhes.empty()
    encontrados_box.empty()

    if not resultados:
        return pd.DataFrame()

    return _normalizar_df_site(pd.concat(resultados, ignore_index=True, sort=False))


def render_origem_site_panel() -> None:
    with st.container(border=True):
        urls, preset = _render_configuracao()

        c1, c2 = st.columns([2, 1])
        with c1:
            executar = st.button("⚡ Buscar produtos agora", key="btn_site_god_mode_buscar", use_container_width=True)
        with c2:
            limpar = st.button("🧹 Limpar captura", key="btn_site_god_mode_limpar", use_container_width=True)

        if limpar:
            _limpar_busca_site()
            st.rerun()

        if executar:
            urls_invalidas = [url for url in urls if not _url_valida(url)]
            if not urls:
                st.error("Informe pelo menos uma URL para iniciar a captura.")
                return
            if urls_invalidas:
                st.error("Corrija as URLs inválidas antes de buscar: " + ", ".join(urls_invalidas[:3]))
                return

            st.info(f"Iniciando busca em {len(urls)} URL(s), fallback {preset.nome}.")
            df_resultado = _executar_busca(urls, preset)

            if df_resultado.empty:
                st.warning("Nenhum produto foi encontrado. Tente uma URL de categoria/produto mais específica ou use o modo Profundo.")
                return

            _guardar_resultado_site(df_resultado, urls, preset)
            log_debug(f"Captura por site finalizada com {len(df_resultado)} produto(s).", nivel="INFO")
            st.success(f"Captura concluída: {len(df_resultado)} produto(s) encontrados.")
            st.rerun()

        _render_preview_existente()
