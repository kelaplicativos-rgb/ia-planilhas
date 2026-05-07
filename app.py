from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.high_quality_image_patch import install_high_quality_image_patch
from bling_app_zero.core.image_url_guard_patch import install_image_url_guard_patch
from bling_app_zero.core.mapping_dropdown_patch import install_mapping_dropdown_patch
from bling_app_zero.core.mega_product_patch import install_mega_product_patch
from bling_app_zero.ui.debug_panel import add_debug_log, render_debug_panel


PATCH_SESSION_KEY = "_bling_runtime_patches_installed_v2"


def _run_stable_app_safe() -> None:
    try:
        from bling_app_zero.stable.stable_app_live_patch import run_stable_app
        run_stable_app()
    except Exception as exc:
        add_debug_log(f"Falha crítica na execução do app: {exc}", origem="APP", nivel="ERRO")
        st.error("O app encontrou um erro interno, mas não caiu. Copie o detalhe abaixo para correção.")
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def _install_runtime_patches_once() -> None:
    """Instala monkey patches apenas uma vez por sessão Streamlit.

    Antes os patches eram reinstalados a cada rerun, deixando o app pesado e
    poluindo o debug com mensagens repetidas.
    """
    if st.session_state.get(PATCH_SESSION_KEY):
        return

    installers = (
        ("Image URL guard patch", install_image_url_guard_patch),
        ("Mega product patch", install_mega_product_patch),
        ("High quality image patch", install_high_quality_image_patch),
        ("Mapping dropdown patch", install_mapping_dropdown_patch),
    )

    for label, installer in installers:
        try:
            installer()
            add_debug_log(f"{label} instalado.", origem="PATCH")
        except Exception as exc:
            add_debug_log(f"Falha ao instalar {label}: {exc}", origem="PATCH", nivel="ERRO")

    st.session_state[PATCH_SESSION_KEY] = True


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas Bling",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    add_debug_log("Aplicação iniciada/renderizada.", origem="APP")
    render_debug_panel()
    _install_runtime_patches_once()
    _run_stable_app_safe()


if __name__ == "__main__":
    main()
