from __future__ import annotations

from typing import Any

import streamlit as st

ETAPAS_VALIDAS_ORIGEM = {"conexao", "origem", "mapeamento", "final", "envio"}
OPERACOES_VALIDAS = {"Cadastro de Produtos", "Atualização de Estoque"}
TIPOS_OPERACAO_BLING = {"cadastro", "estoque"}


def safe_str(valor: Any) -> str:
    try:
        texto = str(valor or "").strip()
        return "" if texto.lower() in {"none", "nan", "nat"} else texto
    except Exception:
        return ""


def safe_int(valor: Any, default: int = 0) -> int:
    try:
        return int(valor)
    except Exception:
        return int(default)


def garantir_estado_origem() -> None:
    defaults = {
        "etapa_origem": "origem",
        "etapa": "origem",
        "etapa_fluxo": "origem",
        "tipo_operacao": "Cadastro de Produtos",
        "tipo_operacao_radio": "Cadastro de Produtos",
        "tipo_operacao_bling": "cadastro",
        "origem_dados_tipo": "planilha",
        "origem_dados_radio": "Planilha / CSV / XML",
        "site_processado": False,
        "df_origem": None,
        "df_saida": None,
        "df_final": None,
        "df_precificado": None,
        "df_calc_precificado": None,
        "deposito_nome": "",
        "coluna_precificacao_resultado": "",
        "margem_bling": 0.0,
        "impostos_bling": 0.0,
        "custofixo_bling": 0.0,
        "taxaextra_bling": 0.0,
        "site_url": "",
        "site_usuario": "",
        "site_senha": "",
        "site_precisa_login": False,
        "site_modo_sincronizacao": "manual",
        "site_delay_segundos": 300,
        "site_estoque_padrao_disponivel": 1,
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    if safe_str(st.session_state.get("tipo_operacao_radio")) not in OPERACOES_VALIDAS:
        st.session_state["tipo_operacao_radio"] = "Cadastro de Produtos"

    if safe_str(st.session_state.get("tipo_operacao")) not in OPERACOES_VALIDAS:
        st.session_state["tipo_operacao"] = "Cadastro de Produtos"

    if safe_str(st.session_state.get("tipo_operacao_bling")) not in TIPOS_OPERACAO_BLING:
        st.session_state["tipo_operacao_bling"] = "cadastro"

    etapa_atual = safe_str(st.session_state.get("etapa_origem") or "origem").lower()
    if etapa_atual not in ETAPAS_VALIDAS_ORIGEM:
        etapa_atual = "origem"

    set_etapa_origem(etapa_atual)


def set_etapa_origem(etapa: str) -> None:
    etapa_normalizada = safe_str(etapa or "origem").lower()
    if etapa_normalizada not in ETAPAS_VALIDAS_ORIGEM:
        etapa_normalizada = "origem"

    st.session_state["etapa_origem"] = etapa_normalizada
    st.session_state["etapa"] = etapa_normalizada
    st.session_state["etapa_fluxo"] = etapa_normalizada


def sincronizar_tipo_operacao(operacao: str) -> None:
    operacao_normalizada = safe_str(operacao or "Cadastro de Produtos")
    if operacao_normalizada not in OPERACOES_VALIDAS:
        operacao_normalizada = "Cadastro de Produtos"

    st.session_state["tipo_operacao"] = operacao_normalizada
    st.session_state["tipo_operacao_bling"] = (
        "cadastro" if operacao_normalizada == "Cadastro de Produtos" else "estoque"
    )


def obter_origem_atual() -> str:
    return safe_str(st.session_state.get("origem_dados_tipo") or "planilha").lower()


def reset_site_processado() -> None:
    st.session_state["site_processado"] = False
