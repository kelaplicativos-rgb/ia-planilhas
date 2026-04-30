from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from bling_app_zero.core.instant_scraper import run_scraper as run_autonomous_scraper
from bling_app_zero.core.instant_scraper.exhaustive_engine import ExhaustiveConfig, run_exhaustive_capture
from bling_app_zero.core.site_crawler import CrawlConfig, crawl_site
from bling_app_zero.ui.app_helpers import log_debug, normalizar_imagens_pipe
from bling_app_zero.ui.site_auth_panel import get_site_auth_context, render_site_auth_panel
from bling_app_zero.ui.site_capture_normalizer import normalizar_captura_site_para_bling


@dataclass(frozen=True)
class ScraperPreset:
    nome: str
    descricao: str
    max_urls: int
    max_products: int
    max_depth: int
    timeout: int
    sleep_seconds: float
    exhaustive_products: int
    exhaustive_pages: int
    browser_pages: int


PRESETS: dict[str, ScraperPreset] = {
    "Seguro": ScraperPreset("Seguro", "Captura estável com checkpoint. Ideal para Streamlit Cloud.", 250, 500, 2, 15, 0.12, 1200, 80, 20),
    "Rápido": ScraperPreset("Rápido", "Teste rápido para validar URL, cookie e estrutura.", 80, 160, 1, 10, 0.05, 300, 30, 8),
    "Profundo": ScraperPreset("Profundo", "Busca maior para fornecedor completo. Usa checkpoint para não perder progresso.", 800, 2500, 4, 22, 0.10, 5000, 300, 80),
    "Sem limite prático": ScraperPreset("Sem limite prático", "Varredura máxima. Pode demorar bastante, mas salva checkpoint durante a execução.", 1500, 6000, 5, 28, 0.08, 12000, 700, 150),
}


COLUNAS_PRIORITARIAS = [
    "Código", "Codigo produto *", "SKU", "Descrição", "Descrição Produto", "Descrição Curta", "Nome",
    "Preço unitário (OBRIGATÓRIO)", "Preço de Custo", "Preço", "Balanço (OBRIGATÓRIO)", "Estoque",
    "Deposito (OBRIGATÓRIO)", "Depósito", "GTIN", "GTIN **", "URL", "Imagens", "Imagem",
    "url_produto", "sku", "descricao", "nome", "preco", "estoque", "quantidade_real", "estoque_origem",
    "gtin", "imagem", "imagens", "agente_estrategia", "agente_score",
]


CHAVES_LIMPAR_SITE = [
    "df_origem", "origem_upload_nome", "origem_upload_bytes", "origem_upload_tipo", "origem_upload_ext",
    "origem_site_url", "origem_site_urls", "origem_site_total_produtos", "origem_site_status",
    "origem_site_ultima_busca", "origem_site_config", "origem_site_checkpoint",
    "origem_site_urls_descobertas", "origem_site_urls_processadas",
]


def _deposito_atual() -> str:
    for chave in ["deposito_nome", "nome_deposito", "deposito", "estoque_deposito_nome"]:
        valor = str(st.session_state.get(chave, "") or "").strip()
        if valor:
            return valor
    return ""


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

    for coluna_preco in ["Preço", "preco", "preco_venda", "valor", "Preço unitário (OBRIGATÓRIO)", "Preço de Custo"]:
        if coluna_preco in base.columns:
            base[coluna_preco] = base[coluna_preco].apply(_normalizar_numero)

    for coluna in base.columns:
        nome = coluna.lower()
        if "imagem" in nome or nome in {"imagens", "url imagem", "url imagens", "image", "img"}:
            base[coluna] = base[coluna].apply(normalizar_imagens_pipe)

    base = normalizar_captura_site_para_bling(base, deposito_nome=_deposito_atual())

    if base.empty:
        return pd.DataFrame()

    existentes = [c for c in COLUNAS_PRIORITARIAS if c in base.columns]
    restantes = [c for c in base.columns if c not in existentes]
    return base[existentes + restantes].reset_index(drop=True).fillna("")


def _config_from_preset(preset: ScraperPreset) -> CrawlConfig:
    return CrawlConfig(
        max_urls=int(preset.max_urls), max_products=int(preset.max_products), max_depth=int(preset.max_depth),
        timeout=int(preset.timeout), sleep_seconds=float(preset.sleep_seconds),
    )


def _exhaustive_config_from_preset(preset: ScraperPreset) -> ExhaustiveConfig:
    return ExhaustiveConfig(
        max_product_urls=int(preset.exhaustive_products), max_base_pages=int(preset.exhaustive_pages),
        max_browser_pages=int(preset.browser_pages), min_score=45, save_every=25,
    )


def _guardar_resultado_site(df: pd.DataFrame, urls: list[str], preset: ScraperPreset, *, motor: str, checkpoint: str = "", urls_descobertas: int = 0, urls_processadas: int = 0) -> None:
    df_normalizado = _normalizar_df_site(df)
    st.session_state["df_origem"] = df_normalizado
    st.session_state["df_saida"] = df_normalizado.copy()
    st.session_state["origem_upload_nome"] = " | ".join(urls)
    st.session_state["origem_upload_bytes"] = b""
    st.session_state["origem_upload_tipo"] = "site"
    st.session_state["origem_upload_ext"] = "site"
    st.session_state["origem_site_url"] = urls[0] if urls else ""
    st.session_state["site_fornecedor_url"] = urls[0] if urls else ""
    st.session_state["origem_site_urls"] = urls
    st.session_state["origem_site_total_produtos"] = int(len(df_normalizado))
    st.session_state["origem_site_ultima_busca"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    st.session_state["origem_site_checkpoint"] = checkpoint
    st.session_state["origem_site_urls_descobertas"] = int(urls_descobertas or 0)
    st.session_state["origem_site_urls_processadas"] = int(urls_processadas or 0)
    st.session_state["origem_site_config"] = {
        "preset": preset.nome,
        "max_urls": preset.max_urls,
        "max_products": preset.max_products,
        "max_depth": preset.max_depth,
        "exhaustive_products": preset.exhaustive_products,
        "exhaustive_pages": preset.exhaustive_pages,
        "browser_pages": preset.browser_pages,
        "motor": motor,
        "normalizador": "site_capture_normalizer",
    }


def _limpar_busca_site() -> None:
    for chave in CHAVES_LIMPAR_SITE + ["site_fornecedor_url", "df_saida"]:
        st.session_state.pop(chave, None)
    log_debug("Resultado da busca por site limpo pelo usuário.", nivel="INFO")


def _render_cards_status(df: pd.DataFrame) -> None:
    total = int(len(df)) if isinstance(df, pd.DataFrame) else 0
    col_preco = "Preço unitário (OBRIGATÓRIO)" if isinstance(df, pd.DataFrame) and "Preço unitário (OBRIGATÓRIO)" in df.columns else "Preço" if isinstance(df, pd.DataFrame) and "Preço" in df.columns else "preco" if isinstance(df, pd.DataFrame) and "preco" in df.columns else ""
    col_img = "Imagens" if isinstance(df, pd.DataFrame) and "Imagens" in df.columns else "imagens" if isinstance(df, pd.DataFrame) and "imagens" in df.columns else "imagem" if isinstance(df, pd.DataFrame) and "imagem" in df.columns else ""
    col_estoque = "Balanço (OBRIGATÓRIO)" if isinstance(df, pd.DataFrame) and "Balanço (OBRIGATÓRIO)" in df.columns else "Estoque" if isinstance(df, pd.DataFrame) and "Estoque" in df.columns else "estoque" if isinstance(df, pd.DataFrame) and "estoque" in df.columns else ""
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
    df = _normalizar_df_site(df)
    st.session_state["df_origem"] = df
    st.session_state["df_saida"] = df.copy()
    st.success(f"Resultado carregado: {len(df)} produto(s) prontos para o próximo passo.")
    _render_cards_status(df)
    checkpoint = str(st.session_state.get("origem_site_checkpoint", "") or "")
    urls_descobertas = int(st.session_state.get("origem_site_urls_descobertas", 0) or 0)
    urls_processadas = int(st.session_state.get("origem_site_urls_processadas", 0) or 0)
    if checkpoint or urls_descobertas or urls_processadas:
        st.caption(f"Checkpoint: {checkpoint or '-'} | URLs descobertas: {urls_descobertas} | URLs processadas: {urls_processadas}")
    with st.expander("👁️ Preview da captura", expanded=True):
        st.dataframe(df.head(120), use_container_width=True)
    csv = df.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("📥 Baixar CSV da captura do site", data=csv, file_name="captura_site_fornecedor.csv", mime="text/csv", use_container_width=True, key="download_captura_site_csv")


def _render_configuracao() -> tuple[list[str], ScraperPreset, str]:
    st.markdown("#### 🚀 Captura por site — Final integrada")
    st.caption("Modo completo: Cookie Bot seguro + captura exaustiva com checkpoint + normalização Bling-ready.")
    texto_inicial = "\n".join(st.session_state.get("origem_site_urls", [])) or str(st.session_state.get("origem_site_url", "") or "")
    urls_texto = st.text_area("URLs para varrer", value=texto_inicial, height=110, key="origem_site_urls_textarea", placeholder="https://site.com/categoria\nhttps://site.com/produto/exemplo")
    urls = _extrair_urls(urls_texto)
    primeira_url = urls[0] if urls else ""
    render_site_auth_panel(primeira_url)
    c1, c2 = st.columns([1, 1])
    with c1:
        preset_nome = st.selectbox("Modo de captura", options=list(PRESETS.keys()), index=2, key="origem_site_preset")
    with c2:
        motor = st.selectbox("Motor principal", options=["Exaustivo com checkpoint", "Agente rápido", "Fallback crawler"], index=0, key="origem_site_motor_principal")
    st.info(PRESETS[preset_nome].descricao)
    return urls, PRESETS[preset_nome], motor


def _executar_busca_exaustiva(urls: list[str], preset: ScraperPreset) -> pd.DataFrame:
    progress = st.progress(0)
    status = st.empty()
    detalhes = st.empty()
    auth_context = get_site_auth_context()
    resultados: list[pd.DataFrame] = []
    ultimo_checkpoint = ""
    total_descobertas = 0
    total_processadas = 0
    total_urls = max(len(urls), 1)
    for idx, url in enumerate(urls, start=1):
        base_percent = int(((idx - 1) / total_urls) * 100)
        status.info(f"Captura exaustiva {idx}/{len(urls)}: {url}")
        def _callback(percentual: int, mensagem: str, total: int) -> None:
            parcial = base_percent + int((max(0, min(int(percentual or 0), 100)) / total_urls))
            progress.progress(max(0, min(parcial, 100)))
            detalhes.caption(str(mensagem or "Capturando..."))
            st.session_state["origem_site_status"] = str(mensagem or "")
        try:
            result = run_exhaustive_capture(url, auth_context=auth_context, config=_exhaustive_config_from_preset(preset), progress_callback=_callback)
            df_url = _normalizar_df_site(result.dataframe)
            ultimo_checkpoint = result.checkpoint_path or ultimo_checkpoint
            total_descobertas += int(result.urls_discovered or 0)
            total_processadas += int(result.urls_processed or 0)
            if not df_url.empty:
                df_url["URL origem da busca"] = url
                resultados.append(df_url)
                log_debug(f"Captura exaustiva encontrou {len(df_url)} produto(s) em {url}. Checkpoint: {result.checkpoint_path}", nivel="INFO")
            else:
                log_debug(f"Captura exaustiva sem resultado em {url}. Status: {result.status}", nivel="AVISO")
        except Exception as exc:
            log_debug(f"Falha na captura exaustiva em {url}: {exc}", nivel="ERRO")
            st.warning(f"Falha na captura exaustiva em {url}: {exc}")
    progress.progress(100)
    status.success("Captura exaustiva finalizada.")
    detalhes.empty()
    st.session_state["origem_site_checkpoint"] = ultimo_checkpoint
    st.session_state["origem_site_urls_descobertas"] = int(total_descobertas)
    st.session_state["origem_site_urls_processadas"] = int(total_processadas)
    if not resultados:
        return pd.DataFrame()
    return _normalizar_df_site(pd.concat(resultados, ignore_index=True, sort=False))


def _executar_busca_agente(urls: list[str]) -> pd.DataFrame:
    progress = st.progress(0)
    status = st.empty()
    resultados: list[pd.DataFrame] = []
    total_urls = max(len(urls), 1)
    auth_context = get_site_auth_context()
    for idx, url in enumerate(urls, start=1):
        status.info(f"Agente rápido {idx}/{len(urls)}: {url}")
        try:
            df_url = run_autonomous_scraper(url, auth_context=auth_context)
        except TypeError:
            df_url = run_autonomous_scraper(url)
        except Exception as exc:
            log_debug(f"Falha no agente rápido em {url}: {exc}", nivel="ERRO")
            df_url = pd.DataFrame()
        df_url = _normalizar_df_site(df_url)
        if not df_url.empty:
            df_url["URL origem da busca"] = url
            resultados.append(df_url)
            log_debug(f"Agente rápido capturou {len(df_url)} produto(s) em {url}", nivel="INFO")
        else:
            log_debug(f"Agente rápido não encontrou produtos em {url}", nivel="AVISO")
        progress.progress(max(0, min(int((idx / total_urls) * 100), 100)))
    status.success("Agente rápido finalizado.")
    if not resultados:
        return pd.DataFrame()
    return _normalizar_df_site(pd.concat(resultados, ignore_index=True, sort=False))


def _executar_busca_crawler(urls: list[str], preset: ScraperPreset) -> pd.DataFrame:
    progress = st.progress(0)
    status = st.empty()
    detalhes = st.empty()
    encontrados_box = st.empty()
    resultados: list[pd.DataFrame] = []
    total_urls = max(len(urls), 1)
    for idx, url in enumerate(urls, start=1):
        base_percent = int(((idx - 1) / total_urls) * 100)
        status.info(f"Fallback crawler {idx}/{len(urls)}: {url}")
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
    status.success("Fallback crawler finalizado.")
    detalhes.empty()
    encontrados_box.empty()
    if not resultados:
        return pd.DataFrame()
    return _normalizar_df_site(pd.concat(resultados, ignore_index=True, sort=False))


def _executar_busca(urls: list[str], preset: ScraperPreset, motor: str) -> pd.DataFrame:
    if motor == "Agente rápido":
        return _executar_busca_agente(urls)
    if motor == "Fallback crawler":
        return _executar_busca_crawler(urls, preset)
    df = _executar_busca_exaustiva(urls, preset)
    if not df.empty:
        return df
    st.warning("Modo exaustivo não encontrou resultado. Tentando agente rápido automaticamente.")
    df = _executar_busca_agente(urls)
    if not df.empty:
        return df
    st.warning("Agente rápido também não encontrou resultado. Tentando fallback crawler.")
    return _executar_busca_crawler(urls, preset)


def render_origem_site_panel() -> None:
    with st.container(border=True):
        urls, preset, motor = _render_configuracao()
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
            st.info(f"Iniciando busca em {len(urls)} URL(s), modo {preset.nome}, motor {motor}.")
            df_resultado = _executar_busca(urls, preset, motor)
            if df_resultado.empty:
                st.warning("Nenhum produto foi encontrado. Para site logado, valide o cookie no Cookie Bot e rode novamente.")
                return
            checkpoint = str(st.session_state.get("origem_site_checkpoint", "") or "")
            urls_descobertas = int(st.session_state.get("origem_site_urls_descobertas", 0) or 0)
            urls_processadas = int(st.session_state.get("origem_site_urls_processadas", 0) or 0)
            _guardar_resultado_site(df_resultado, urls, preset, motor=motor, checkpoint=checkpoint, urls_descobertas=urls_descobertas, urls_processadas=urls_processadas)
            log_debug(f"Captura por site finalizada com {len(df_resultado)} produto(s). Motor: {motor}. Normalizador Bling-ready aplicado.", nivel="INFO")
            st.success(f"Captura concluída: {len(df_resultado)} produto(s) encontrados.")
            st.rerun()
        _render_preview_existente()
