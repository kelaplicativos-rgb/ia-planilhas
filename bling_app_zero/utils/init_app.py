
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st


# ============================================================
# PLAYWRIGHT CONTROLE
# ============================================================

PLAYWRIGHT_MARKER_DIR = Path("bling_app_zero/output")
PLAYWRIGHT_MARKER_DIR.mkdir(parents=True, exist_ok=True)

PLAYWRIGHT_OK_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_browser_ok.marker"


def _log(msg: str) -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore
        log_debug(msg)
    except Exception:
        print(f"[INIT_APP] {msg}")


def _playwright_instalado() -> bool:
    try:
        import playwright  # noqa
        return True
    except Exception:
        return False


def _browser_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


def _instalar_browser():
    """
    Resolve erro clássico do Streamlit Cloud:
    Playwright instalado, mas Chromium não.
    """

    if not _playwright_instalado():
        return

    if PLAYWRIGHT_OK_MARKER.exists():
        return

    if _browser_ok():
        PLAYWRIGHT_OK_MARKER.write_text("ok")
        return

    _log("Instalando Chromium do Playwright...")

    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
        )

        if _browser_ok():
            PLAYWRIGHT_OK_MARKER.write_text("ok")
            _log("Playwright Chromium OK")
        else:
            _log("Falha ao validar Chromium após instalação")

    except Exception as e:
        _log(f"Erro ao instalar Chromium: {e}")


# ============================================================
# INIT APP
# ============================================================

def init_app() -> None:
    """
    Inicialização global do estado do app
    """

    # ============================================================
    # BOOTSTRAP PLAYWRIGHT (CRÍTICO)
    # ============================================================

    if "_playwright_bootstrap" not in st.session_state:
        st.session_state["_playwright_bootstrap"] = True
        _instalar_browser()

    # ============================================================
    # ETAPA PRINCIPAL
    # ============================================================

    if "etapa" not in st.session_state:
        st.session_state["etapa"] = "origem"

    if "etapa_origem" not in st.session_state:
        st.session_state["etapa_origem"] = "origem"

    if "etapa_fluxo" not in st.session_state:
        st.session_state["etapa_fluxo"] = "origem"

    if "etapa_historico" not in st.session_state:
        st.session_state["etapa_historico"] = []

    # ============================================================
    # CONTROLE URL
    # ============================================================

    if "_etapa_url_inicializada" not in st.session_state:
        st.session_state["_etapa_url_inicializada"] = False

    if "_ultima_etapa_sincronizada_url" not in st.session_state:
        st.session_state["_ultima_etapa_sincronizada_url"] = "origem"

    # ============================================================
    # DATAFRAMES
    # ============================================================

    defaults_df = [
        "df_origem",
        "df_normalizado",
        "df_precificado",
        "df_mapeado",
        "df_saida",
        "df_final",
        "df_calc_precificado",
        "df_preview_mapeamento",
        "df_modelo",
    ]

    for chave in defaults_df:
        if chave not in st.session_state:
            st.session_state[chave] = None

    # ============================================================
    # UPLOAD
    # ============================================================

    for key in [
        "origem_upload_nome",
        "origem_upload_bytes",
        "origem_upload_tipo",
        "origem_upload_ext",
        "modelo_upload_nome",
        "modelo_upload_bytes",
        "modelo_upload_tipo",
        "modelo_upload_ext",
    ]:
        if key not in st.session_state:
            st.session_state[key] = ""

    # ============================================================
    # CONFIG
    # ============================================================

    if "tipo_operacao" not in st.session_state:
        st.session_state["tipo_operacao"] = ""

    if "tipo_operacao_bling" not in st.session_state:
        st.session_state["tipo_operacao_bling"] = ""

    if "deposito_nome" not in st.session_state:
        st.session_state["deposito_nome"] = ""

    # ============================================================
    # PRECIFICAÇÃO
    # ============================================================

    defaults_precificacao = {
        "pricing_coluna_custo": "",
        "pricing_custo_fixo": 0.0,
        "pricing_frete_fixo": 0.0,
        "pricing_taxa_extra": 0.0,
        "pricing_impostos_percent": 0.0,
        "pricing_margem_percent": 0.0,
        "pricing_outros_percent": 0.0,
        "pricing_valor_teste": 0.0,
        "pricing_df_preview": None,
        "pricing_aplicada_ok": False,
    }

    for chave, valor in defaults_precificacao.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    # ============================================================
    # MAPEAMENTO
    # ============================================================

    if "mapping_manual" not in st.session_state:
        st.session_state["mapping_manual"] = {}

    if "mapping_sugerido" not in st.session_state:
        st.session_state["mapping_sugerido"] = {}

    if "mapping_hash_base" not in st.session_state:
        st.session_state["mapping_hash_base"] = ""

    if "mapping_hash_modelo" not in st.session_state:
        st.session_state["mapping_hash_modelo"] = ""

    # ============================================================
    # BLING
    # ============================================================

    if "bling_conectado" not in st.session_state:
        st.session_state["bling_conectado"] = False

    if "bling_status_texto" not in st.session_state:
        st.session_state["bling_status_texto"] = "Desconectado"

    if "bling_envio_resultado" not in st.session_state:
        st.session_state["bling_envio_resultado"] = None

    # ============================================================
    # FLAGS
    # ============================================================

    if "_fluxo_inicializado" not in st.session_state:
        st.session_state["_fluxo_inicializado"] = True
