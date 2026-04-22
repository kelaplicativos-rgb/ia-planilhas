from __future__ import annotations

import os
from pathlib import Path

import streamlit as st


# ============================================================
# PLAYWRIGHT / MODO HÍBRIDO
# ============================================================

PLAYWRIGHT_MARKER_DIR = Path("bling_app_zero/output")
PLAYWRIGHT_MARKER_DIR.mkdir(parents=True, exist_ok=True)

PLAYWRIGHT_OK_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_browser_ok.marker"
PLAYWRIGHT_FAIL_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_browser_fail.marker"


def _log(msg: str) -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore

        log_debug(msg)
    except Exception:
        print(f"[INIT_APP] {msg}")


def _bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "sim"}


def _playwright_modulo_instalado() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except Exception:
        return False


def _playwright_browser_ok() -> bool:
    """
    Valida o browser APENAS se o uso de Playwright estiver explicitamente habilitado.
    Não tenta instalar nada.
    Não deve travar bootstrap do app.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            browser.close()
        return True
    except Exception as exc:
        _log(f"[PLAYWRIGHT] Browser indisponível no ambiente: {exc}")
        return False


def _detectar_modo_crawler() -> dict[str, object]:
    """
    Define o modo de operação do crawler sem instalar Chromium no boot.

    Regras:
    - HTTP/Híbrido é o padrão.
    - Playwright só entra se o ambiente permitir E se estiver habilitado por env.
    - Nunca quebrar a inicialização por causa de browser.
    """
    playwright_habilitado = _bool_env("BLING_ENABLE_PLAYWRIGHT", default=False)
    modulo_instalado = _playwright_modulo_instalado()

    status = {
        "playwright_habilitado": playwright_habilitado,
        "playwright_modulo_instalado": modulo_instalado,
        "playwright_browser_ok": False,
        "crawler_runtime_mode": "http_hybrid",
        "crawler_browser_disponivel": False,
        "crawler_forcar_http": True,
    }

    if not playwright_habilitado:
        _log("[PLAYWRIGHT] Desabilitado no bootstrap. Sistema em modo HTTP híbrido.")
        return status

    if not modulo_instalado:
        _log("[PLAYWRIGHT] Módulo não instalado. Sistema em modo HTTP híbrido.")
        return status

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
        _log("[PLAYWRIGHT] Browser validado. Sistema em modo híbrido com navegador opcional.")
    else:
        try:
            PLAYWRIGHT_FAIL_MARKER.write_text("fail", encoding="utf-8")
        except Exception:
            pass
        _log("[PLAYWRIGHT] Browser não validado. Fallback HTTP híbrido ativo.")

    return status


def _bootstrap_crawler_runtime() -> None:
    """
    Faz o bootstrap uma única vez por sessão.
    Não instala Chromium.
    Não roda subprocess.
    Não derruba o app.
    """
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


# ============================================================
# INIT APP
# ============================================================

def init_app() -> None:
    """
    Inicialização global do estado do app.
    """

    # ============================================================
    # BOOTSTRAP CRAWLER (SEM INSTALAR CHROMIUM)
    # ============================================================

    _bootstrap_crawler_runtime()

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
