import secrets

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
        "bling_user_key": "",
        "bling_account_label": "",
        "bling_last_message": "",
        "bling_last_message_type": "",
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    if not st.session_state.get("bling_user_key"):
        st.session_state["bling_user_key"] = f"bling_user_{secrets.token_hex(8)}"
