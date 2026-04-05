import streamlit as st


def init_state() -> None:
    estados_padrao = {
        "logs": [],
        "df_saida": None,
        "df_origem": None,
        "df_origem_hash": None,
        "origem_atual": "",
        "origem_arquivo_nome": "",
        "validacao_erros": [],
        "validacao_avisos": [],
        "validacao_ok": False,
        "ultima_chave_arquivo": None,
        "mapeamento_memoria": {},
        "mapeamento_manual": {},
        "preco_compra_modulo_precificacao": 0.0,
        "preco_venda_calculado": 0.0,
        "ultimo_log_envio": [],
    }

    for chave, valor_padrao in estados_padrao.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor_padrao
