from __future__ import annotations

import streamlit as st

from bling_app_zero.core.high_quality_image_patch import install_high_quality_image_patch
from bling_app_zero.core.mega_product_patch import install_mega_product_patch
from bling_app_zero.stable.stable_app import run_stable_app
from bling_app_zero.ui.debug_panel import (
    add_debug_log,
    render_debug_panel,
    render_debug_panel_inline,
)


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas Bling",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    add_debug_log("Aplicação iniciada/renderizada.", origem="APP")
    render_debug_panel()
    render_debug_panel_inline()

    install_mega_product_patch()
    add_debug_log("Mega product patch instalado.", origem="PATCH")

    install_high_quality_image_patch()
    add_debug_log("High quality image patch instalado.", origem="PATCH")

    run_stable_app()


if __name__ == "__main__":
    main()
