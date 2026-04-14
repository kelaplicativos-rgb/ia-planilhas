from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd
import streamlit as st

ETAPAS_VALIDAS_ORIGEM = {"conexao", "origem", "mapeamento", "final", "envio"}


# ==========================================================
# HELPERS BÁSICOS
# ==========================================================


def safe_str(valor: Any) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def safe_int(valor: Any, default: int = 0) -> int:
    try:
        if valor is None:
            return default
        if isinstance(valor, str) and not valor.strip():
            return default
        return int(float(valor))
    except Exception:
        return default


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


def _safe_copy_df(df: Any) -> Any:
    try:
        if isinstance(df, pd.DataFrame):
            return df.copy()
        return df
    except Exception:
        return df


def _normalizar_fluxo(valor: Any, default: str = "conexao") -> str:
    etapa = safe_str(valor or default).lower()
    if etapa not in ETAPAS_VALIDAS_ORIGEM:
        return default
    return etapa


def _normalizar_tipo_origem(valor: Any, default: str = "") -> str:
    texto = safe_str(valor or default).strip().lower()

    mapa = {
        "site": "site",
        "buscar em site": "site",
        "busca em site": "site",
        "origem por site": "site",
        "buscar no site": "site",
        "planilha": "planilha",
        "planilha / csv / xml": "planilha",
        "planilha/csv/xml": "planilha",
        "arquivo": "planilha",
        "upload": "planilha",
        "anexar planilha": "planilha",
        "planilha, csv ou xml": "planilha",
    }

    if texto in mapa:
        return mapa[texto]

    if "site" in texto:
        return "site"

    if any(token in texto for token in ["planilha", "csv", "xml", "arquivo", "upload"]):
        return "planilha"

    return default


# ==========================================================
# ETAPA / FLUXO
# ==========================================================


def _set_etapa_global(valor: str) -> None:
    etapa = _normalizar_fluxo(valor, "conexao")
    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def set_etapa_origem(valor: str) -> None:
    _set_etapa_global(valor)


# ==========================================================
# ORIGEM / OPERAÇÃO
# ==========================================================


def obter_origem_atual() -> str:
    try:
        candidatos = [
            st.session_state.get("origem_dados_tipo"),
            st.session_state.get("origem_dados"),
            st.session_state.get("origem_dados_radio"),
            st.session_state.get("_origem_anterior_origem_dados"),
        ]

        for candidato in candidatos:
            origem = _normalizar_tipo_origem(candidato)
            if origem:
                return origem

        return ""
    except Exception:
        return ""


def _tipo_operacao_para_bling(operacao: str) -> str:
    texto = safe_str(operacao).lower()
    if "estoque" in texto:
        return "estoque"
    return "cadastro"


def sincronizar_tipo_operacao(operacao: str) -> None:
    """
    IMPORTANTE:
    Não escrever em st.session_state["tipo_operacao_radio"] aqui,
    porque essa chave pertence ao st.radio já criado na UI.
    """
    operacao_limpa = safe_str(operacao) or "Cadastro de Produtos"
    tipo_bling = _tipo_operacao_para_bling(operacao_limpa)
    operacao_anterior = safe_str(st.session_state.get("_operacao_anterior_origem_dados"))

    st.session_state["tipo_operacao"] = operacao_limpa
    st.session_state["tipo_operacao_bling"] = tipo_bling

    if not operacao_anterior:
        st.session_state["_operacao_anterior_origem_dados"] = operacao_limpa
        return

    if operacao_anterior == operacao_limpa:
        return

    resetar_estado_fluxo(preservar_origem=True)
    st.session_state["_operacao_anterior_origem_dados"] = operacao_limpa


# ==========================================================
# SITE
# ==========================================================


def reset_site_processado() -> None:
    st.session_state["site_processado"] = False
    st.session_state["site_autoavanco_realizado"] = False


# ==========================================================
# WIDGETS / LIMPEZA
# ==========================================================


def limpar_mapeamento_widgets() -> None:
    try:
        chaves_para_remover = [
            chave
            for chave in list(st.session_state.keys())
            if str(chave).startswith("map_")
        ]
        for chave in chaves_para_remover:
            st.session_state.pop(chave, None)

        st.session_state.pop("mapping_origem", None)
    except Exception:
        pass


def resetar_estado_fluxo(preservar_origem: bool = True) -> None:
    df_origem = _safe_copy_df(st.session_state.get("df_origem"))
    fp_origem = safe_str(st.session_state.get("origem_dados_fingerprint"))
    origem_tipo = _normalizar_tipo_origem(st.session_state.get("_origem_anterior_origem_dados"))
    origem_radio = _normalizar_tipo_origem(st.session_state.get("origem_dados_tipo"))
    origem_dados = _normalizar_tipo_origem(st.session_state.get("origem_dados"))

    chaves_limpar = [
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "df_modelo_mapeamento",
        "preview_download_df",
        "site_autoavanco_realizado",
    ]

    for chave in chaves_limpar:
        st.session_state.pop(chave, None)

    limpar_mapeamento_widgets()

    if preservar_origem and safe_df_dados(df_origem):
        st.session_state["df_origem"] = df_origem.copy()

    if fp_origem:
        st.session_state["origem_dados_fingerprint"] = fp_origem

    if origem_tipo:
        st.session_state["_origem_anterior_origem_dados"] = origem_tipo

    if origem_radio:
        st.session_state["origem_dados_tipo"] = origem_radio

    if origem_dados:
        st.session_state["origem_dados"] = origem_dados


# ==========================================================
# FINGERPRINT / SINCRONIZAÇÃO
# ==========================================================


def fingerprint_df(df: pd.DataFrame) -> str:
    try:
        if not isinstance(df, pd.DataFrame):
            return ""

        base = {
            "shape": tuple(df.shape),
            "columns": [str(c) for c in list(df.columns)],
            "head": df.head(10).fillna("").astype(str).to_dict(),
        }
        bruto = str(base).encode("utf-8", errors="ignore")
        return hashlib.md5(bruto).hexdigest()
    except Exception:
        return ""


# ==========================================================
# ESTADO BASE
# ==========================================================


def garantir_estado_origem() -> None:
    defaults = {
        "etapa_origem": "conexao",
        "etapa": "conexao",
        "etapa_fluxo": "conexao",
        "tipo_operacao": "Cadastro de Produtos",
        "tipo_operacao_bling": "cadastro",
        "tipo_operacao_radio": "Cadastro de Produtos",
        "origem_dados_tipo": "",
        "origem_dados": "",
        "_origem_anterior_origem_dados": "",
        "_operacao_anterior_origem_dados": "",
        "deposito_nome": "",
        "quantidade_fallback": 0,
        "site_processado": False,
        "site_autoavanco_realizado": False,
        "site_url": "",
        "site_precisa_login": False,
        "site_usuario": "",
        "site_senha": "",
        "site_modo_sincronizacao": "manual",
        "site_delay_segundos": 300,
        "site_estoque_padrao_disponivel": 1,
        "coluna_precificacao_resultado": "",
        "margem_bling": 0.0,
        "impostos_bling": 0.0,
        "custofixo_bling": 0.0,
        "taxaextra_bling": 0.0,
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    origem_atual = obter_origem_atual()
    if origem_atual:
        st.session_state["origem_dados_tipo"] = origem_atual
        st.session_state["origem_dados"] = origem_atual
        if not safe_str(st.session_state.get("_origem_anterior_origem_dados")):
            st.session_state["_origem_anterior_origem_dados"] = origem_atual

    etapa_atual = _normalizar_fluxo(st.session_state.get("etapa_origem"), "conexao")
    _set_etapa_global(etapa_atual)
    
