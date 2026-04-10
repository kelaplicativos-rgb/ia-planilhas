from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


ETAPAS_VALIDAS = {"origem", "mapeamento", "final", "envio"}


def safe_df_dados(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty
    except Exception:
        return False


def safe_df_estrutura(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def garantir_estado_origem() -> None:
    try:
        etapa_atual = str(st.session_state.get("etapa_origem") or "").strip().lower()
        if etapa_atual not in ETAPAS_VALIDAS:
            st.session_state["etapa_origem"] = "origem"
    except Exception:
        st.session_state["etapa_origem"] = "origem"

    if "etapa" not in st.session_state:
        st.session_state["etapa"] = st.session_state.get("etapa_origem", "origem")

    if "etapa_fluxo" not in st.session_state:
        st.session_state["etapa_fluxo"] = st.session_state.get("etapa_origem", "origem")

    if "origem_dados" not in st.session_state:
        st.session_state["origem_dados"] = ""

    if "tipo_operacao_bling" not in st.session_state:
        st.session_state["tipo_operacao_bling"] = ""


def set_etapa_origem(etapa: str) -> None:
    etapa_norm = str(etapa or "origem").strip().lower()
    if etapa_norm not in ETAPAS_VALIDAS:
        etapa_norm = "origem"

    st.session_state["etapa_origem"] = etapa_norm
    st.session_state["etapa"] = etapa_norm
    st.session_state["etapa_fluxo"] = etapa_norm


def limpar_fluxo_processado() -> None:
    for chave in [
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "mapping_origem",
        "mapeamento_sugerido",
        "preview_final_valido",
        "campos_obrigatorios_faltantes",
        "campos_obrigatorios_alertas",
    ]:
        if chave in st.session_state:
            del st.session_state[chave]


def limpar_origem_carregada() -> None:
    for chave in [
        "df_origem",
        "df_dados",
        "arquivo_origem_nome",
        "arquivo_origem_hash",
        "origem_dados_nome",
        "origem_dados_hash",
        "origem_dados_tipo_arquivo",
        "origem_pdf_texto",
        "origem_pdf_nome",
        "origem_xml_texto",
        "origem_xml_nome",
        "site_processado",
    ]:
        if chave in st.session_state:
            del st.session_state[chave]


def salvar_origem_no_estado(
    df: pd.DataFrame,
    *,
    origem: str,
    nome_ref: str = "",
    hash_ref: str = "",
    texto_bruto: str = "",
) -> None:
    origem_norm = str(origem or "").strip().lower()

    st.session_state["df_origem"] = df.copy()
    st.session_state["df_dados"] = df.copy()
    st.session_state["origem_dados"] = origem_norm
    st.session_state["origem_dados_nome"] = str(nome_ref or "")
    st.session_state["origem_dados_hash"] = str(hash_ref or "")
    st.session_state["arquivo_origem_nome"] = str(nome_ref or "")
    st.session_state["arquivo_origem_hash"] = str(hash_ref or "")
    st.session_state["origem_dados_tipo_arquivo"] = origem_norm

    if origem_norm == "pdf":
        st.session_state["origem_pdf_texto"] = texto_bruto
        st.session_state["origem_pdf_nome"] = str(nome_ref or "")

    if origem_norm == "xml":
        st.session_state["origem_xml_texto"] = texto_bruto
        st.session_state["origem_xml_nome"] = str(nome_ref or "")


def controlar_troca_origem(origem: str, logger=None) -> bool:
    garantir_estado_origem()

    origem_nova = str(origem or "").strip().lower()
    origem_atual = str(st.session_state.get("origem_dados") or "").strip().lower()

    if origem_nova == origem_atual:
        return False

    limpar_origem_carregada()
    limpar_fluxo_processado()

    st.session_state["origem_dados"] = origem_nova
    set_etapa_origem("origem")

    if callable(logger):
        logger(
            f"[ORIGEM_ESTADO] troca de origem: {origem_atual or '-'} -> {origem_nova or '-'}",
            "INFO",
        )

    return True


def controlar_troca_operacao(operacao: str, logger=None) -> bool:
    garantir_estado_origem()

    valor = str(operacao or "").strip().lower()

    if valor in {"cadastro", "cadastro de produtos"}:
        tipo_novo = "cadastro"
    elif valor in {"estoque", "atualização de estoque", "atualizacao de estoque"}:
        tipo_novo = "estoque"
    else:
        return False

    tipo_atual = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    if tipo_novo == tipo_atual:
        return False

    st.session_state["tipo_operacao_bling"] = tipo_novo
    limpar_fluxo_processado()

    if "df_modelo_mapeamento" in st.session_state:
        del st.session_state["df_modelo_mapeamento"]

    set_etapa_origem("origem")

    if callable(logger):
        logger(
            f"[ORIGEM_ESTADO] troca de operação: {tipo_atual or '-'} -> {tipo_novo}",
            "INFO",
        )

    return True


def sincronizar_estado_com_origem(df_origem: pd.DataFrame, logger=None) -> None:
    garantir_estado_origem()

    if not safe_df_estrutura(df_origem):
        return

    st.session_state["df_origem"] = df_origem.copy()
    st.session_state["df_dados"] = df_origem.copy()

    if not safe_df_estrutura(st.session_state.get("df_saida")):
        st.session_state["df_saida"] = df_origem.copy()

    if not safe_df_estrutura(st.session_state.get("df_final")):
        st.session_state["df_final"] = st.session_state["df_saida"].copy()

    if callable(logger):
        logger(
            f"[ORIGEM_ESTADO] origem sincronizada com {len(df_origem)} linha(s) e {len(df_origem.columns)} coluna(s).",
            "INFO",
        )
