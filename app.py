import streamlit as st

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.bling_panel import (
    render_bling_panel,
    render_bling_import_panel,
)
from bling_app_zero.ui.precificacao_panel import render_precificacao_panel
from bling_app_zero.ui.envio_panel import render_send_panel


st.set_page_config(
    page_title="Bling Manual PRO",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def aplicar_estilo_global() -> None:
    st.markdown(
        """
        <style>
        /* ===== Espaçamento geral ===== */
        .block-container{
            padding-top: 0.8rem;
            padding-bottom: 1rem;
            padding-left: 0.7rem;
            padding-right: 0.7rem;
            max-width: 100%;
        }

        /* ===== Título ===== */
        h1, h2, h3{
            margin-top: 0.2rem !important;
            margin-bottom: 0.6rem !important;
        }

        /* ===== Botões padronizados ===== */
        div.stButton > button,
        div.stDownloadButton > button {
            width: 100%;
            min-height: 42px;
            height: 42px;
            border-radius: 10px;
            font-size: 0.95rem;
            font-weight: 600;
            padding: 0 0.8rem;
        }

        /* ===== Inputs mais compactos ===== */
        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        div[data-testid="stTextArea"] textarea {
            min-height: 40px;
        }

        /* ===== Tabs ===== */
        div[data-testid="stTabs"] button {
            border-radius: 10px;
            min-height: 40px;
            font-weight: 600;
        }

        /* ===== Expander ===== */
        details {
            border-radius: 10px;
        }

        /* ===== Dataframes e editors ===== */
        div[data-testid="stDataFrame"],
        div[data-testid="stDataEditor"] {
            border-radius: 10px;
            overflow: hidden;
        }

        /* ===== Celular ===== */
        @media (max-width: 768px) {
            .block-container{
                padding-top: 0.55rem;
                padding-bottom: 0.8rem;
                padding-left: 0.45rem;
                padding-right: 0.45rem;
            }

            h1{
                font-size: 1.35rem !important;
                line-height: 1.2 !important;
            }

            h2{
                font-size: 1.10rem !important;
            }

            h3{
                font-size: 1rem !important;
            }

            div.stButton > button,
            div.stDownloadButton > button {
                min-height: 38px;
                height: 38px;
                font-size: 0.88rem;
                border-radius: 9px;
                padding: 0 0.55rem;
            }

            div[data-testid="stTabs"] button {
                min-height: 38px;
                font-size: 0.82rem;
                padding-left: 0.55rem;
                padding-right: 0.55rem;
            }

            div[data-testid="stMetricValue"]{
                font-size: 1rem !important;
            }

            div[data-testid="stMetricLabel"]{
                font-size: 0.78rem !important;
            }

            p, label, .stCaption {
                font-size: 0.86rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    init_state()
    aplicar_estilo_global()

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
