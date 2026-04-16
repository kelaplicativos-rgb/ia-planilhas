
from __future__ import annotations

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS = {"origem", "precificacao", "mapeamento", "final"}


def log_debug(mensagem: str, nivel: str = "INFO") -> None:
    logs = st.session_state.setdefault("debug_logs", [])
    logs.append({"nivel": nivel, "mensagem": str(mensagem)})
    st.session_state["debug_logs"] = logs[-200:]


def safe_df_estrutura(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def safe_df_dados(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def garantir_estado_base() -> None:
    defaults = {
        "etapa": "origem",
        "etapa_global": "origem",
        "tipo_operacao": "Cadastro de Produtos",
        "tipo_operacao_bling": "cadastro",
        "origem_dados": "planilha",
        "fornecedor_nome": "",
        "fornecedor_url": "",
        "fornecedor_busca": "",
        "df_origem": None,
        "df_precificado": None,
        "df_saida": None,
        "df_final": None,
        "df_busca_site": None,
        "debug_logs": [],
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def obter_etapa_global() -> str:
    etapa = str(st.session_state.get("etapa_global") or st.session_state.get("etapa") or "origem").strip().lower()
    if etapa not in ETAPAS_VALIDAS:
        etapa = "origem"
    return etapa


def sincronizar_etapa_global(etapa: str) -> None:
    etapa = str(etapa or "origem").strip().lower()
    if etapa not in ETAPAS_VALIDAS:
        etapa = "origem"
    st.session_state["etapa"] = etapa
    st.session_state["etapa_global"] = etapa


def ir_para_etapa(etapa: str) -> None:
    sincronizar_etapa_global(etapa)
    st.rerun()


def render_debug_panel() -> None:
    st.write("**Etapa atual:**", obter_etapa_global())
    st.write("**Operação:**", st.session_state.get("tipo_operacao"))
    st.write("**Origem:**", st.session_state.get("origem_dados"))

    for chave in ["df_origem", "df_precificado", "df_saida", "df_final", "df_busca_site"]:
        valor = st.session_state.get(chave)
        if isinstance(valor, pd.DataFrame):
            st.write(f"**{chave}:** {valor.shape[0]} linhas x {valor.shape[1]} colunas")
        else:
            st.write(f"**{chave}:** vazio")

    logs = st.session_state.get("debug_logs", [])
    if logs:
        st.write("**Logs recentes**")
        for item in logs[-30:]:
            st.write(f"[{item.get('nivel', 'INFO')}] {item.get('mensagem', '')}")
