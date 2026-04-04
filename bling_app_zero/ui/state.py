import streamlit as st


def init_state() -> None:
    defaults = {
        "df_origem": None,
        "origem_atual": "",
        "mapeamento_manual": {},
        "preco_compra_modulo_precificacao": 0.0,
        "bling_produtos_df": None,
        "bling_estoque_df": None,
        "ultimo_log_envio": [],
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor
