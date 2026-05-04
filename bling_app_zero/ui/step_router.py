from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.mod_kernel import call


ROUTES = {
    "origem": ("bling_app_zero.ui.origem", "render_origem_dados"),
    "hub": ("bling_app_zero.ui.hub_dashboard", "render_hub_dashboard"),
    "precificacao": ("bling_app_zero.ui.precificacao", "render_origem_precificacao"),
    "mapeamento": ("bling_app_zero.ui.mapeamento", "render_origem_mapeamento"),
    "preview_final": ("bling_app_zero.ui.preview", "render_preview_final"),
}


def render_step(step: str) -> None:
    module, name = ROUTES.get(step, ROUTES["origem"])
    try:
        call(module, name)
    except Exception as exc:
        st.error("Não foi possível carregar esta etapa.")
        st.caption(f"Etapa: {step} | Módulo: {module}.{name}")
        st.exception(exc)
