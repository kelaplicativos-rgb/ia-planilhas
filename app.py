from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.stable.stable_app import run_stable_app


def install_exit_guard() -> None:
    components.html(
        """
        <script>
        window.addEventListener('beforeunload', function (event) {
            event.preventDefault();
            event.returnValue = '';
        });
        </script>
        """,
        height=0,
    )


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas Bling",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    install_exit_guard()
    run_stable_app()


if __name__ == "__main__":
    main()
