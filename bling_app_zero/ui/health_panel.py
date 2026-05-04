from __future__ import annotations

import streamlit as st

from bling_app_zero.healthcheck import run_healthcheck


def render_health_panel() -> None:
    with st.expander("Diagnóstico do sistema", expanded=False):
        result = run_healthcheck()
        if result.get("success"):
            st.success("Núcleo modular carregado com sucesso.")
        else:
            st.error("Foram encontrados problemas no núcleo modular.")

        errors = result.get("errors") or {}
        if errors:
            st.json(errors)
        else:
            st.caption("Rotas, hooks e módulos principais disponíveis.")

        legacy = result.get("legacy_modules_present") or []
        if legacy:
            st.caption("Legados controlados ainda presentes para fallback/migração gradual:")
            st.json(legacy)
