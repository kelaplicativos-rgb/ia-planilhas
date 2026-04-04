import streamlit as st


def init_state() -> None:
    defaults = {
        "df_origem": None,
        "origem_atual": "",
        "modo_operacao": "Cadastro de produtos",
        "mapeamento_manual": {},
        "preco_compra_modulo_precificacao": 0.0,
        "bling_produtos_df": None,
        "bling_estoque_df": None,
        "ultimo_log_envio": [],
        "deposito_padrao": "",
        "origem_urls_texto": "",
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor
