from __future__ import annotations

import traceback

import streamlit as st

APP_VERSION = "3.1.0-clean-core"


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas Bling",
        page_icon="✅",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    try:
        from bling_app_zero.clean_core.app import run_clean_app
        run_clean_app()
    except Exception as exc:
        st.error("Erro interno no Clean Core.")
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


if __name__ == "__main__":
    main()
