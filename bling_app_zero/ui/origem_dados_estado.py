from __future__ import annotations

import hashlib
from typing import Any

import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


def safe_df_dados(df: Any) -> bool:
    try:
        return (
            df is not None
            and hasattr(df, "columns")
            and len(df.columns) > 0
            and not getattr(df, "empty", True)
        )
    except Exception:
        return False


def _safe_str(valor: Any) -> str:
    try:
        texto = str(valor or "").strip()
        if texto.lower() in {"none", "nan", "<na>", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _normalizar_valor_fluxo(valor: Any) -> str:
    return _safe_str(valor).lower()


def fingerprint_df(df: Any) -> str:
    try:
        if not safe_df_dados(df):
            return ""

        base = f"{list(df.columns)}|{len(df)}"
        return hashlib.md5(base.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def limpar_mapeamento_widgets() -> None:
    for chave in list(st.session_state.keys()):
        if str(chave).startswith("map_"):
            st.session_state.pop(chave, None)


def resetar_estado_fluxo(manter_modelos: bool = True) -> None:
    """
    🔥 CORREÇÃO PRO:
    Só reseta se NÃO tiver dados ainda
    """

    if safe_df_dados(st.session_state.get("df_saida")):
        # 🔒 NÃO RESETAR se já tem dados
        return

    chaves_reset = [
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "mapeamento_manual",
        "mapeamento_auto",
        "mapeamento_colunas",
        "colunas_mapeadas",
    ]

    for chave in chaves_reset:
        st.session_state.pop(chave, None)

    limpar_mapeamento_widgets()
    st.session_state["etapa_origem"] = "origem"


# =========================
# 🔥 CORREÇÃO PRINCIPAL
# =========================
def controlar_troca_operacao(operacao: str, log_debug) -> None:
    operacao_atual = _safe_str(operacao)
    operacao_anterior = _safe_str(
        st.session_state.get("_operacao_anterior_origem_dados")
    )

    if not operacao_anterior:
        st.session_state["_operacao_anterior_origem_dados"] = operacao_atual
        return

    if operacao_anterior == operacao_atual:
        return

    # 🔥 NOVA REGRA:
    if safe_df_dados(st.session_state.get("df_saida")):
        log_debug(
            f"Operação alterada (IGNORADA RESET): '{operacao_anterior}' → '{operacao_atual}'",
            "WARNING",
        )
        st.session_state["_operacao_anterior_origem_dados"] = operacao_atual
        return

    log_debug(
        f"Operação alterada (RESET REAL): '{operacao_anterior}' → '{operacao_atual}'",
        "INFO",
    )

    resetar_estado_fluxo()
    st.session_state["_operacao_anterior_origem_dados"] = operacao_atual


def controlar_troca_origem(origem: str, log_debug) -> None:
    origem_atual = _normalizar_valor_fluxo(origem)
    origem_anterior = _normalizar_valor_fluxo(
        st.session_state.get("_origem_anterior_origem_dados")
    )

    if not origem_anterior:
        st.session_state["_origem_anterior_origem_dados"] = origem_atual
        return

    if origem_anterior == origem_atual:
        return

    # 🔥 MESMA PROTEÇÃO
    if safe_df_dados(st.session_state.get("df_saida")):
        log_debug("Troca de origem ignorada (dados já existem)", "WARNING")
        st.session_state["_origem_anterior_origem_dados"] = origem_atual
        return

    resetar_estado_fluxo()
    st.session_state["_origem_anterior_origem_dados"] = origem_atual


def sincronizar_estado_com_origem(df_origem, log_debug) -> None:
    if not safe_df_dados(df_origem):
        return

    fingerprint = fingerprint_df(df_origem)
    atual = _safe_str(st.session_state.get("origem_dados_fingerprint"))

    if not atual:
        st.session_state["origem_dados_fingerprint"] = fingerprint
        st.session_state["df_origem"] = df_origem.copy()
        st.session_state["df_saida"] = df_origem.copy()
        st.session_state["df_final"] = df_origem.copy()
        return

    if atual != fingerprint:
        log_debug("Nova origem detectada", "INFO")

        st.session_state["origem_dados_fingerprint"] = fingerprint
        st.session_state["df_origem"] = df_origem.copy()
        st.session_state["df_saida"] = df_origem.copy()
        st.session_state["df_final"] = df_origem.copy()

        limpar_mapeamento_widgets()
