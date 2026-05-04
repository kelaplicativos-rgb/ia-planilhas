from __future__ import annotations

import streamlit as st

from bling_app_zero.compact_healthcheck import run_compact_healthcheck


def render_health_panel() -> None:
    with st.expander("Diagnóstico do sistema", expanded=False):
        result = run_compact_healthcheck()
        if result.get("success"):
            st.success("Fluxo compacto carregado com sucesso.")
        else:
            st.error("Foram encontrados problemas no fluxo compacto.")

        errors = result.get("core_errors") or {}
        if errors:
            st.json(errors)
        else:
            st.caption("Origem, mapeamento, exportação e uploader inteligente disponíveis.")

        missing = result.get("reader_engines_missing") or {}
        if missing:
            st.warning("Algumas engines opcionais de leitura não estão instaladas neste deploy.")
            st.json(missing)
        else:
            st.caption("Engines de leitura de anexos disponíveis.")
