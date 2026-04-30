from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from bling_app_zero.utils.architecture_guard import check_imports

PLAYWRIGHT_MARKER_DIR = Path("bling_app_zero/output")
PLAYWRIGHT_MARKER_DIR.mkdir(parents=True, exist_ok=True)

PLAYWRIGHT_OK_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_browser_ok.marker"
PLAYWRIGHT_FAIL_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_browser_fail.marker"
PLAYWRIGHT_INSTALL_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_chromium_install_attempted.marker"
PLAYWRIGHT_DEPS_MARKER = PLAYWRIGHT_MARKER_DIR / "playwright_deps_install_attempted.marker"


def _log(msg: str) -> None:
    try:
        from bling_app_zero.ui.app_helpers import log_debug  # type: ignore
        log_debug(msg)
    except Exception:
        print(f"[INIT_APP] {msg}")


def init_app() -> None:
    # 🔥 HARDENING: valida arquitetura antes de tudo
    result = check_imports()
    if not result.ok:
        st.error("Falha crítica na arquitetura/imports:")
        for err in result.errors[:10]:
            st.code(err)
        st.stop()

    if "logs" not in st.session_state:
        st.session_state["logs"] = []

    if "etapa" not in st.session_state:
        st.session_state["etapa"] = "origem"
    if "etapa_origem" not in st.session_state:
        st.session_state["etapa_origem"] = "origem"
    if "etapa_fluxo" not in st.session_state:
        st.session_state["etapa_fluxo"] = "origem"

    for chave in [
        "df_origem",
        "df_normalizado",
        "df_precificado",
        "df_mapeado",
        "df_saida",
        "df_final",
    ]:
        if chave not in st.session_state:
            st.session_state[chave] = None
