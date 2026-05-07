from __future__ import annotations

import traceback

import streamlit as st


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas Bling",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    try:
        from bling_app_zero.rebuild.app_rebuild import run_rebuild_app
        run_rebuild_app()
    except Exception as exc:
        st.error("O app encontrou um erro interno no rebuild.")
        st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


if __name__ == "__main__":
    main()
