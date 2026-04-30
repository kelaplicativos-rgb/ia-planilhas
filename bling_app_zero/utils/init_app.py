from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st


PLAYWRIGHT_MARKER_DIR = Path("bling_app_zero/output")
PLAYWRIGHT_MARKER_DIR.mkdir(parents=True, exist_ok=True)

PLAYWRIGHT_OK_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_browser_ok.marker"
PLAYWRIGHT_FAIL_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_browser_fail.marker"
PLAYWRIGHT_INSTALL_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_chromium_install_attempted.marker"


def _log(msg: str) -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore
        log_debug(msg)
    except Exception:
        print(f"[INIT_APP] {msg}")


def _playwright_modulo_instalado() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


def _instalar_chromium_runtime() -> None:
    """Tenta baixar o Chromium do Playwright no runtime do Streamlit Cloud.

    O Streamlit Cloud nem sempre executa postBuild. Então este fallback roda
    uma única vez por container quando o browser ainda não existe.
    """
    if PLAYWRIGHT_INSTALL_MARKER.exists():
        return

    if not _playwright_modulo_instalado():
        return

    try:
        _log("[PLAYWRIGHT] Chromium ausente. Tentando instalar em runtime...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            timeout=180,
        )
        PLAYWRIGHT_INSTALL_MARKER.write_text("ok", encoding="utf-8")
        _log("[PLAYWRIGHT] Chromium instalado em runtime com sucesso.")
    except Exception as exc:
        try:
            PLAYWRIGHT_INSTALL_MARKER.write_text("fail", encoding="utf-8")
        except Exception:
            pass
        _log(f"[PLAYWRIGHT] Falha ao instalar Chromium em runtime: {exc}")


def _playwright_browser_ok() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                ],
            )
            browser.close()
        return True
    except Exception as exc:
        _log(f"[PLAYWRIGHT] Browser indisponível no ambiente: {exc}")
        return False


def _detectar_modo_crawler() -> dict[str, object]:
    modulo_instalado = _playwright_modulo_instalado()

    status = {
        "playwright_habilitado": True,
        "playwright_modulo_instalado": modulo_instalado,
        "playwright_browser_ok": False,
        "crawler_runtime_mode": "http_hybrid",
        "crawler_browser_disponivel": False,
        "crawler_forcar_http": True,
    }

    if not modulo_instalado:
        _log("[PLAYWRIGHT] Módulo não instalado. Rodando em HTTP híbrido.")
        return status

    browser_ok = _playwright_browser_ok()

    if not browser_ok:
        _instalar_chromium_runtime()
        browser_ok = _playwright_browser_ok()

    status["playwright_browser_ok"] = browser_ok
    status["crawler_browser_disponivel"] = browser_ok
    status["crawler_forcar_http"] = not browser_ok

    if browser_ok:
        status["crawler_runtime_mode"] = "hybrid_browser"
        try:
            PLAYWRIGHT_OK_MARKER.write_text("ok", encoding="utf-8")
        except Exception:
            pass
        _log("[PLAYWRIGHT] Browser ATIVO. Sistema com JS habilitado 🚀")
    else:
        try:
            PLAYWRIGHT_FAIL_MARKER.write_text("fail", encoding="utf-8")
        except Exception:
            pass
        _log("[PLAYWRIGHT] Browser não disponível. Fallback HTTP ativo.")

    return status


def _bootstrap_crawler_runtime() -> None:
    if st.session_state.get("_crawler_runtime_bootstrap_done"):
        return

    st.session_state["_crawler_runtime_bootstrap_done"] = True

    status = _detectar_modo_crawler()
    for chave, valor in status.items():
        st.session_state[chave] = valor

    st.session_state["site_runtime_modo"] = str(status.get("crawler_runtime_mode", "http_hybrid"))
    st.session_state["site_runtime_http_first"] = True
    st.session_state["site_runtime_browser_opcional"] = bool(status.get("crawler_browser_disponivel", False))

    _log(
        "[CRAWLER] Bootstrap concluído | "
        f"modo={st.session_state['site_runtime_modo']} | "
        f"http_first={st.session_state['site_runtime_http_first']} | "
        f"browser_opcional={st.session_state['site_runtime_browser_opcional']}"
    )


def init_app() -> None:
    _bootstrap_crawler_runtime()

    if "etapa" not in st.session_state:
        st.session_state["etapa"] = "origem"

    if "etapa_origem" not in st.session_state:
        st.session_state["etapa_origem"] = "origem"

    if "etapa_fluxo" not in st.session_state:
        st.session_state["etapa_fluxo"] = "origem"

    if "etapa_historico" not in st.session_state:
        st.session_state["etapa_historico"] = []

    if "_etapa_url_inicializada" not in st.session_state:
        st.session_state["_etapa_url_inicializada"] = False

    if "_ultima_etapa_sincronizada_url" not in st.session_state:
        st.session_state["_ultima_etapa_sincronizada_url"] = "origem"

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
