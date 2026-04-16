
from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS = {"origem", "precificacao", "mapeamento", "final"}


def log_debug(mensagem: str, nivel: str = "INFO") -> None:
    logs = st.session_state.setdefault("debug_logs", [])
    logs.append({"nivel": str(nivel), "mensagem": str(mensagem)})
    st.session_state["debug_logs"] = logs[-300:]


def normalizar_coluna_busca(valor: Any) -> str:
    texto = str(valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def safe_df_estrutura(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def safe_df_dados(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty
    except Exception:
        return False


def garantir_estado_base() -> None:
    defaults = {
        "etapa": "origem",
        "etapa_global": "origem",
        "operacao": "cadastro",
        "tipo_operacao": "Cadastro de Produtos",
        "tipo_operacao_radio": "Cadastro de Produtos",
        "tipo_operacao_bling": "cadastro",
        "origem_dados": "planilha",
        "origem_tipo": "",
        "origem_tipo_radio": "Planilha fornecedora",
        "origem_site_url": "",
        "padrao_disponivel_site": 10,
        "origem_fornecedor_api": "",
        "origem_categoria_api": "",
        "fornecedor_nome": "",
        "fornecedor_url": "",
        "fornecedor_busca": "",
        "deposito_nome": "",
        "df_origem": None,
        "df_modelo": None,
        "df_modelo_operacao": None,
        "colunas_modelo": None,
        "df_precificado": None,
        "df_calc_precificado": None,
        "df_mapeado": None,
        "df_preview_mapeamento": None,
        "df_saida": None,
        "df_final": None,
        "df_busca_site": None,
        "mapping_origem": {},
        "mapping_origem_rascunho": {},
        "mapping_origem_defaults": {},
        "debug_logs": [],
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def obter_etapa_global() -> str:
    etapa = str(
        st.session_state.get("etapa_global")
        or st.session_state.get("etapa")
        or "origem"
    ).strip().lower()

    if etapa not in ETAPAS_VALIDAS:
        etapa = "origem"

    return etapa


def get_etapa() -> str:
    return obter_etapa_global()


def sincronizar_etapa_global(etapa: str) -> None:
    etapa_normalizada = str(etapa or "origem").strip().lower()
    if etapa_normalizada not in ETAPAS_VALIDAS:
        etapa_normalizada = "origem"

    st.session_state["etapa"] = etapa_normalizada
    st.session_state["etapa_global"] = etapa_normalizada


def ir_para_etapa(etapa: str) -> None:
    sincronizar_etapa_global(etapa)
    st.rerun()


def render_debug_panel() -> None:
    st.write("**Etapa atual:**", obter_etapa_global())
    st.write("**Operação:**", st.session_state.get("tipo_operacao"))
    st.write("**Origem:**", st.session_state.get("origem_tipo") or st.session_state.get("origem_dados"))

    for chave in [
        "df_origem",
        "df_modelo",
        "df_modelo_operacao",
        "df_precificado",
        "df_calc_precificado",
        "df_mapeado",
        "df_preview_mapeamento",
        "df_saida",
        "df_final",
        "df_busca_site",
    ]:
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
