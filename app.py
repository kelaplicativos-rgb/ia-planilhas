from __future__ import annotations

import streamlit as st

APP_VERSION = "3.0.1-cleanup"


def main() -> None:
    st.set_page_config(
        page_title="IA Planilhas Bling",
        page_icon="🧹",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.title("IA Planilhas Bling")
    st.caption(f"Versão {APP_VERSION}")
    st.warning(
        "Sistema em limpeza técnica. O fluxo experimental foi removido para evitar geração de planilhas incorretas."
    )
    st.info(
        "Próximo passo seguro: reconstruir apenas sobre arquivos validados, sem módulos soltos, sem patches em runtime e sem motores misturados."
    )


if __name__ == "__main__":
    main()
