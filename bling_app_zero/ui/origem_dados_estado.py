from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd
import streamlit as st

ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final", "envio"}


# ==========================================================
# VALIDAÇÃO DF
# ==========================================================
def safe_df_dados(df: Any) -> bool:
    try:
        return (
            isinstance(df, pd.DataFrame)
            and len(df.columns) > 0
            and not df.empty
        )
    except Exception:
        return False


def safe_df_estrutura(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    try:
        texto = str(valor or "").strip()
        if texto.lower() in {"none", "nan", "", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _normalizar_valor_fluxo(valor: Any) -> str:
    return _safe_str(valor).lower()


def _safe_copy_df(df: Any) -> Any:
    try:
        if isinstance(df, pd.DataFrame):
            return df.copy()
        return df
    except Exception:
        return df


# ==========================================================
# UPLOAD / MODELO ATIVO
# ==========================================================
def tem_upload_ativo() -> bool:
    try:
        return bool(
            safe_df_estrutura(st.session_state.get("df_modelo_cadastro"))
            or safe_df_estrutura(st.session_state.get("df_modelo_estoque"))
            or safe_df_estrutura(st.session_state.get("df_origem"))
        )
    except Exception:
        return False


# ==========================================================
# FINGERPRINT
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
# ETAPA
# ==========================================================
def _set_etapa_global(valor: str) -> None:
    etapa = _normalizar_valor_fluxo(valor or "origem")
    if etapa not in ETAPAS_VALIDAS_ORIGEM:
        etapa = "origem"

    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def set_etapa_origem(valor: str) -> None:
    _set_etapa_global(valor)


# ==========================================================
# LIMPEZA DE WIDGETS / MAPEAMENTO
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
    fp_origem = _safe_str(st.session_state.get("origem_dados_fingerprint"))
    origem_tipo = _safe_str(st.session_state.get("_origem_anterior_origem_dados"))

    chaves_limpar = [
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "df_modelo_mapeamento",
        "preview_download_df",
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


# ==========================================================
# CONTROLE DE OPERAÇÃO
# ==========================================================
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

    log_debug(
        f"Operação alterada: {operacao_anterior} → {operacao_atual}. "
        f"Resetando saída/mapeamento e preservando origem.",
        "INFO",
    )

    resetar_estado_fluxo(preservar_origem=True)
    st.session_state["_operacao_anterior_origem_dados"] = operacao_atual


# ==========================================================
# CONTROLE DE ORIGEM
# ==========================================================
def controlar_troca_origem(origem: str, log_debug) -> None:
    """
    Blindagem principal:
    trocar a origem na interface não deve apagar imediatamente os dados já carregados.
    A limpeza real só deve acontecer quando um NOVO df_origem for efetivamente carregado
    e o fingerprint mudar em sincronizar_estado_com_origem().
    """
    origem_atual = _safe_str(origem)
    origem_anterior = _safe_str(
        st.session_state.get("_origem_anterior_origem_dados")
    )

    if not origem_anterior:
        st.session_state["_origem_anterior_origem_dados"] = origem_atual
        st.session_state["_origem_trocada_manual"] = False
        return

    if origem_anterior == origem_atual:
        return

    log_debug(
        f"Origem alterada: {origem_anterior} → {origem_atual}. "
        f"Preservando dados atuais até uma nova carga real da origem.",
        "INFO",
    )

    # Não apagar df_origem / df_saida / df_final aqui.
    # Isso evita perder tudo ao apenas voltar de etapa.
    st.session_state["_origem_anterior_origem_dados"] = origem_atual
    st.session_state["_origem_trocada_manual"] = True
    st.session_state["site_processado"] = False


# ==========================================================
# ESTADO BASE
# ==========================================================
def garantir_estado_origem() -> None:
    defaults = {
        "etapa_origem": "origem",
        "etapa": "origem",
        "etapa_fluxo": "origem",
        "tipo_operacao_bling": "",
        "deposito_nome": "",
        "quantidade_fallback": 0,
        "site_processado": False,
        "_origem_trocada_manual": False,
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    etapa_atual = _normalizar_valor_fluxo(
        st.session_state.get("etapa_origem", "origem")
    )
    if etapa_atual not in ETAPAS_VALIDAS_ORIGEM:
        etapa_atual = "origem"

    _set_etapa_global(etapa_atual)


# ==========================================================
# SINCRONIZAÇÃO DA ORIGEM
# ==========================================================
def sincronizar_estado_com_origem(df_origem, log_debug) -> None:
    if not safe_df_dados(df_origem):
        return

    fp_novo = fingerprint_df(df_origem)
    fp_atual = _safe_str(st.session_state.get("origem_dados_fingerprint"))
    houve_troca_manual = bool(st.session_state.get("_origem_trocada_manual", False))

    if not fp_atual:
        st.session_state["origem_dados_fingerprint"] = fp_novo
        st.session_state["df_origem"] = df_origem.copy()

        # Só semeia df_saida/df_final se eles ainda não existirem.
        if not safe_df_estrutura(st.session_state.get("df_saida")):
            st.session_state["df_saida"] = df_origem.copy()

        if not safe_df_estrutura(st.session_state.get("df_final")):
            st.session_state["df_final"] = df_origem.copy()

        st.session_state["_origem_trocada_manual"] = False
        return

    if fp_atual != fp_novo:
        log_debug("Nova origem real detectada. Limpando saída anterior.", "INFO")

        st.session_state["origem_dados_fingerprint"] = fp_novo
        st.session_state["df_origem"] = df_origem.copy()

        # Aqui sim limpa porque chegou uma NOVA base de dados de verdade.
        for chave in [
            "df_saida",
            "df_final",
            "df_precificado",
            "df_calc_precificado",
        ]:
            st.session_state.pop(chave, None)

        limpar_mapeamento_widgets()
        st.session_state["_origem_trocada_manual"] = False
        return

    # Se o fingerprint não mudou, não limpar nada.
    # Isso cobre o caso de "voltar uma tela" sem trocar os dados reais.
    if houve_troca_manual:
        log_debug(
            "Troca de origem na interface detectada sem nova carga de dados. "
            "Mantendo estado atual preservado.",
            "INFO",
        )
        st.session_state["_origem_trocada_manual"] = False
