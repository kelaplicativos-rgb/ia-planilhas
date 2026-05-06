from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.high_quality_image_patch import install_high_quality_image_patch
from bling_app_zero.core.mega_product_patch import install_mega_product_patch
from bling_app_zero.ui.debug_panel import add_debug_log, render_debug_panel


def _run_stable_app_safe() -> None:
    try:
        from bling_app_zero.stable.stable_app import run_stable_app
        run_stable_app()
    except Exception as exc:
        add_debug_log(f"Falha crítica na execução do app: {exc}", origem="APP", nivel="ERRO")
        st.error("O app encontrou um erro interno, mas não caiu. Copie o detalhe abaixo para correção.")
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas Bling",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    add_debug_log("Aplicação iniciada/renderizada.", origem="APP")
    render_debug_panel()

    try:
        install_mega_product_patch()
        add_debug_log("Mega product patch instalado.", origem="PATCH")
    except Exception as exc:
        add_debug_log(f"Falha ao instalar Mega product patch: {exc}", origem="PATCH", nivel="ERRO")

    try:
        install_high_quality_image_patch()
        add_debug_log("High quality image patch instalado.", origem="PATCH")
    except Exception as exc:
        add_debug_log(f"Falha ao instalar High quality image patch: {exc}", origem="PATCH", nivel="ERRO")

    _run_stable_app_safe()


if __name__ == "__main__":
    main()
