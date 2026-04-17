
from __future__ import annotations

from typing import Any
import time

import pandas as pd

from bling_app_zero.core.site_crawler_cleaners import normalizar_url, safe_str
from bling_app_zero.core.site_crawler_extractors import extrair_detalhes_heuristicos
from bling_app_zero.core.site_crawler_gpt import gpt_extrair_produto
from bling_app_zero.core.site_crawler_http import fetch_html_retry
from bling_app_zero.core.site_crawler_links import descobrir_produtos_no_dominio
from bling_app_zero.core.site_crawler_validators import (
    pontuar_produto,
    produto_final_valido,
    titulo_valido,
)


# ============================================================
# STREAMLIT SAFE
# ============================================================

def _streamlit_ctx():
    try:
        import streamlit as st
        return st
    except Exception:
        return None


def _log(msg: str):
    try:
        from bling_app_zero.ui.app_helpers import log_debug
        log_debug(msg)
    except:
        print(msg)


# ============================================================
# CONTROLE DE LOOP (NOVO 🔥)
# ============================================================

def _deve_continuar_loop() -> bool:
    st = _streamlit_ctx()
    if st is None:
        return False
    return bool(st.session_state.get("site_auto_loop_ativo", False))


# ============================================================
# LIMITES
# ============================================================

def _limite_tecnico(limite_links: int | None) -> int:
    limite_padrao = 8000

    if not isinstance(limite_links, int):
        return limite_padrao

    if limite_links <= 0:
        return limite_padrao

    return min(max(limite_links, 1), limite_padrao)


# ============================================================
# SAÍDA
# ============================================================

def _montar_linha_saida(final: dict) -> dict:
    return {
        "Código": safe_str(final.get("codigo")),
        "Descrição": safe_str(final.get("descricao")),
        "Categoria": safe_str(final.get("categoria")),
        "GTIN": safe_str(final.get("gtin")),
        "NCM": safe_str(final.get("ncm")),
        "Preço de custo": safe_str(final.get("preco")),
        "Quantidade": safe_str(final.get("quantidade")),
        "URL Imagens": safe_str(final.get("url_imagens")),
        "URL Produto": safe_str(final.get("url_produto")),
    }


def _df_saida(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).fillna("")

    if "URL Produto" in df.columns:
        df = df.drop_duplicates(subset=["URL Produto"], keep="first")

    colunas_ordenadas = [
        "Código",
        "Descrição",
        "Categoria",
        "GTIN",
        "NCM",
        "Preço de custo",
        "Quantidade",
        "URL Imagens",
        "URL Produto",
    ]

    for col in colunas_ordenadas:
        if col not in df.columns:
            df[col] = ""

    return df[colunas_ordenadas].reset_index(drop=True)


# ============================================================
# SCORE
# ============================================================

def _score_produto(item: dict) -> int:
    return pontuar_produto(
        titulo=safe_str(item.get("descricao")),
        preco=safe_str(item.get("preco")),
        codigo=safe_str(item.get("codigo")),
        gtin=safe_str(item.get("gtin")),
        imagens=safe_str(item.get("url_imagens")),
        categoria=safe_str(item.get("categoria")),
        url_produto=safe_str(item.get("url_produto")),
    )


# ============================================================
# FUNÇÃO PRINCIPAL (EVOLUÍDA 🔥)
# ============================================================

def buscar_produtos_site_com_gpt(
    base_url: str,
    termo: str = "",
    limite_links: int | None = None,
    diagnostico: bool = False,
    modo_loop: bool = False,
    intervalo_segundos: int = 60,
) -> pd.DataFrame:

    st = _streamlit_ctx()

    base_url = normalizar_url(base_url)
    termo = safe_str(termo)

    if not base_url:
        return pd.DataFrame()

    limite = _limite_tecnico(limite_links)

    # LOOP AUTOMÁTICO 🔥
    if modo_loop:
        _log(f"🚀 MODO LOOP ATIVO no site: {base_url}")

        resultado_final = pd.DataFrame()

        while True:
            if not _deve_continuar_loop():
                _log("⛔ Loop interrompido pelo usuário")
                break

            df = _executar_busca_unica(
                base_url,
                termo,
                limite,
                diagnostico,
            )

            if not df.empty:
                resultado_final = df

                # INTEGRAÇÃO DIRETA COM BLING 🔥
                try:
                    from bling_app_zero.services.bling.bling_sync import enviar_produtos
                    enviar_produtos(df)
                    _log(f"📤 Enviado {len(df)} produtos para o Bling")
                except Exception as e:
                    _log(f"Erro envio Bling: {e}")

            time.sleep(max(5, intervalo_segundos))

        return resultado_final

    # EXECUÇÃO NORMAL
    return _executar_busca_unica(
        base_url,
        termo,
        limite,
        diagnostico,
    )


# ============================================================
# EXECUÇÃO ÚNICA
# ============================================================

def _executar_busca_unica(
    base_url: str,
    termo: str,
    limite: int,
    diagnostico: bool,
) -> pd.DataFrame:

    st = _streamlit_ctx()

    progress_bar = None
    status_box = None

    if st is not None:
        progress_bar = st.progress(0)
        status_box = st.empty()
        status_box.info("🔍 Descobrindo produtos...")

    produtos = descobrir_produtos_no_dominio(
        base_url=base_url,
        termo=termo,
        max_paginas=400,
        max_produtos=limite,
        max_segundos=900,
    )

    if not produtos:
        return pd.DataFrame()

    rows = []
    vistos = set()

    total = len(produtos)

    for i, url in enumerate(produtos, start=1):

        if progress_bar:
            progress_bar.progress(int((i / total) * 100))

        try:
            html = fetch_html_retry(url, tentativas=2)
            heuristica = extrair_detalhes_heuristicos(url, html)
            final = gpt_extrair_produto(url, html, heuristica)

            if not produto_final_valido(final):
                continue

            if url in vistos:
                continue

            rows.append(_montar_linha_saida(final))
            vistos.add(url)

        except Exception as e:
            _log(f"Erro produto: {e}")

    if status_box:
        status_box.success(f"✅ {len(rows)} produtos válidos")

    return _df_saida(rows)
    
