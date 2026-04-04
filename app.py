import streamlit as st

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.bling_panel import (
    render_bling_panel,
    render_bling_import_panel,
)
from bling_app_zero.ui.precificacao_panel import render_precificacao_panel
from bling_app_zero.ui.envio_panel import render_send_panel

st.set_page_config(page_title="Bling Manual PRO", layout="wide")


def main() -> None:
    init_state()

    st.title("Bling Manual PRO")

    aba1, aba2, aba3, aba4 = st.tabs(
        [
            "Origem dos dados",
            "Integração Bling",
            "Precificação",
            "Envio",
        ]
    )

    with aba1:
        render_origem_dados()

    with aba2:
        render_bling_panel()
        st.divider()
        render_bling_import_panel()

    with aba3:
        render_precificacao_panel()

    with aba4:
        render_send_panel()


if __name__ == "__main__":
    main()
