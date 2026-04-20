
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


def _safe_log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore

        log_debug(msg, nivel=nivel)
    except Exception:
        try:
            print(f"[INIT_APP][{nivel}] {msg}")
        except Exception:
            pass


def _playwright_python_instalado() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except Exception:
        return False


def _playwright_browser_disponivel() -> tuple[bool, str]:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _deve_tentar_instalar_browser() -> bool:
    if not _playwright_python_instalado():
        return False

    if PLAYWRIGHT_OK_MARKER.exists():
        return False

    return True


def _marcar_browser_ok() -> None:
    try:
        PLAYWRIGHT_OK_MARKER.write_text("ok", encoding="utf-8")
    except Exception:
        pass


def _marcar_browser_fail(motivo: str) -> None:
    try:
        PLAYWRIGHT_FAIL_MARKER.write_text(str(motivo or "falha"), encoding="utf-8")
    except Exception:
        pass


def _instalar_playwright_chromium() -> None:
    """
    Tenta preparar o browser do Playwright uma única vez por ambiente.
    Isso ajuda no Streamlit Cloud quando a lib Python já está instalada,
    mas o Chromium ainda não foi baixado.
    """
    if not _deve_tentar_instalar_browser():
        return

    ok, detalhe = _playwright_browser_disponivel()
    if ok:
        _safe_log_debug("Browser do Playwright já disponível no ambiente.", nivel="INFO")
        _marcar_browser_ok()
        return

    _safe_log_debug(
        f"Browser do Playwright ausente. Tentando instalar Chromium automaticamente. Detalhe inicial: {detalhe}",
        nivel="INFO",
    )

    comandos = [
        [sys.executable, "-m", "playwright", "install", "chromium"],
    ]

    ultimo_erro = ""
    for comando in comandos:
        try:
            processo = subprocess.run(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=900,
                env=os.environ.copy(),
            )

            if processo.returncode == 0:
                ok_final, detalhe_final = _playwright_browser_disponivel()
                if ok_final:
                    _safe_log_debug("Chromium do Playwright instalado com sucesso.", nivel="INFO")
                    _marcar_browser_ok()
                    return

                ultimo_erro = detalhe_final or "Browser ainda indisponível após instalação."
            else:
                ultimo_erro = (
                    (processo.stderr or "").strip()
                    or (processo.stdout or "").strip()
                    or f"Falha no comando com código {processo.returncode}"
                )
        except Exception as exc:
            ultimo_erro = str(exc)

    _safe_log_debug(
        f"Não foi possível preparar o Chromium do Playwright automaticamente. Motivo: {ultimo_erro}",
        nivel="ERRO",
    )
    _marcar_browser_fail(ultimo_erro)


def init_app() -> None:
    """
    Inicialização global do estado do app.

    PRIORIDADE 1:
    - garantir etapa inicial correta
    - alinhar nomes de estado
    - evitar quebra de fluxo no primeiro render
    - preparar ambiente do Playwright quando disponível
    """

    # ============================================================
    # ETAPA PRINCIPAL (WIZARD)
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
    # CONTROLE DE URL / RERUN (CRÍTICO)
    # ============================================================

    if "_etapa_url_inicializada" not in st.session_state:
        st.session_state["_etapa_url_inicializada"] = False

    if "_ultima_etapa_sincronizada_url" not in st.session_state:
        st.session_state["_ultima_etapa_sincronizada_url"] = "origem"

    # ============================================================
    # DADOS PRINCIPAIS DO FLUXO
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
    # ORIGEM / UPLOAD
    # ============================================================

    if "origem_upload_nome" not in st.session_state:
        st.session_state["origem_upload_nome"] = ""

    if "origem_upload_bytes" not in st.session_state:
        st.session_state["origem_upload_bytes"] = None

    if "origem_upload_tipo" not in st.session_state:
        st.session_state["origem_upload_tipo"] = ""

    if "origem_upload_ext" not in st.session_state:
        st.session_state["origem_upload_ext"] = ""

    if "modelo_upload_nome" not in st.session_state:
        st.session_state["modelo_upload_nome"] = ""

    if "modelo_upload_bytes" not in st.session_state:
        st.session_state["modelo_upload_bytes"] = None

    if "modelo_upload_tipo" not in st.session_state:
        st.session_state["modelo_upload_tipo"] = ""

    if "modelo_upload_ext" not in st.session_state:
        st.session_state["modelo_upload_ext"] = ""

    # ============================================================
    # CONFIGURAÇÃO GERAL
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
    # BLING (CONEXÃO / ENVIO)
    # ============================================================

    if "bling_conectado" not in st.session_state:
        st.session_state["bling_conectado"] = False

    if "bling_status_texto" not in st.session_state:
        st.session_state["bling_status_texto"] = "Desconectado"

    if "bling_envio_resultado" not in st.session_state:
        st.session_state["bling_envio_resultado"] = None

    # ============================================================
    # FLAGS DE CONTROLE DE FLUXO
    # ============================================================

    if "_fluxo_inicializado" not in st.session_state:
        st.session_state["_fluxo_inicializado"] = True

    # ============================================================
    # PLAYWRIGHT / AMBIENTE
    # ============================================================

    if "_playwright_bootstrap_tentado" not in st.session_state:
        st.session_state["_playwright_bootstrap_tentado"] = True
        _instalar_playwright_chromium()
