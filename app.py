from __future__ import annotations

import streamlit as st

from bling_app_zero.core.high_quality_image_patch import install_high_quality_image_patch
from bling_app_zero.core.mega_product_patch import install_mega_product_patch
from bling_app_zero.stable.stable_app import run_stable_app


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas Bling",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    install_mega_product_patch()
    install_high_quality_image_patch()
    run_stable_app()


if __name__ == "__main__":
    main()
