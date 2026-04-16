
from __future__ import annotations

import streamlit as st


def init_app_state() -> None:
    """
    Inicializa o estado global do app já no novo fluxo IA.
    Remove completamente dependências do fluxo manual antigo.
    """

    # ============================================================
    # CONTROLE DE ETAPA (NOVO PADRÃO)
    # ============================================================

    if "etapa" not in st.session_state:
        st.session_state["etapa"] = "ia"

    if "etapa_origem" not in st.session_state:
        st.session_state["etapa_origem"] = "ia"

    if "etapa_fluxo" not in st.session_state:
        st.session_state["etapa_fluxo"] = "ia"

    # ============================================================
    # DADOS PRINCIPAIS
    # ============================================================

    st.session_state.setdefault("df_origem", None)
    st.session_state.setdefault("df_precificado", None)
    st.session_state.setdefault("df_mapeado", None)
    st.session_state.setdefault("df_final", None)
    st.session_state.setdefault("df_saida", None)

    # ============================================================
    # CONTROLE DE FLUXO IA
    # ============================================================

    st.session_state.setdefault("modo_execucao", "ia_orquestrador")
    st.session_state.setdefault("ia_fluxo_ativo", True)

    # ============================================================
    # LIMPEZA DE LIXO DO FLUXO ANTIGO
    # ============================================================

    chaves_antigas = [
        "origem_dados_radio",
        "tipo_operacao",
        "origem_tipo",
        "origem_arquivo",
        "origem_url",
        "modelo_upload",
        "modelo_tipo",
        "modelo_arquivo",
        "precificacao_config",
        "mapeamento_config",
        "colunas_mapeadas",
        "preview_linhas",
    ]

    for chave in chaves_antigas:
        if chave in st.session_state:
            del st.session_state[chave]

    # ============================================================
    # CONTROLE DE DEPÓSITO (ESTOQUE)
    # ============================================================

    st.session_state.setdefault("deposito_nome", "")

    # ============================================================
    # DEBUG
    # ============================================================

    st.session_state.setdefault("debug_logs", [])
