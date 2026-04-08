from __future__ import annotations

import hashlib
from typing import Any

import streamlit as st


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento"}


def safe_df_dados(df: Any) -> bool:
    try:
        if df is None:
            return False
        if not hasattr(df, "columns"):
            return False
        if len(df.columns) == 0:
            return False
        if getattr(df, "empty", True):
            return False
        return True
    except Exception:
        return False


def fingerprint_df(df: Any) -> str:
    try:
        if not safe_df_dados(df):
            return ""

        df_base = df.copy()

        try:
            head_registros = (
                df_base.head(10)
                .fillna("")
                .astype(str)
                .to_dict(orient="records")
            )
        except Exception:
            head_registros = []

        base = f"{list(df_base.columns)}|{len(df_base)}|{head_registros}"
        return hashlib.md5(base.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def limpar_mapeamento_widgets() -> None:
    try:
        for chave in list(st.session_state.keys()):
            if str(chave).startswith("map_"):
                st.session_state.pop(chave, None)
    except Exception:
        pass


def tem_upload_ativo() -> bool:
    try:
        return bool(
            st.session_state.get("modelo_cadastro")
            or st.session_state.get("modelo_estoque")
            or st.session_state.get("arquivo_origem_planilha")
            or st.session_state.get("arquivo_origem_xml")
        )
    except Exception:
        return False


def _pop_varias(chaves: list[str]) -> None:
    for chave in chaves:
        try:
            st.session_state.pop(chave, None)
        except Exception:
            pass


def _set_if_changed(key: str, value):
    try:
        if st.session_state.get(key) != value:
            st.session_state[key] = value
    except Exception:
        pass


def _forcar_etapa_valida():
    """
    Garantia absoluta: nunca deixar etapa inválida quebrar o sistema
    """
    etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()

    if etapa not in ETAPAS_VALIDAS_ORIGEM:
        st.session_state["etapa_origem"] = "origem"


def resetar_estado_fluxo(manter_modelos: bool = True) -> None:
    chaves_reset = [
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "bloquear_campos_auto",
        "mapeamento_automatico",
        "mapeamento_manual",
        "mapeamento_auto",
        "mapeamento_colunas",
        "colunas_mapeadas",
        "df_mapeado",
        "mapeamento_manual_cadastro",
        "mapeamento_manual_estoque",
        "coluna_preco_base",
        "origem_dados_fingerprint",
        "df_origem_site",
        "df_origem_xml",
        "arquivo_origem_hash",
        "arquivo_origem_nome",
        "origem_arquivo_hash",
        "origem_arquivo_nome",
        "origem_dados_hash",
        "origem_dados_nome",
        "url_origem_site",
    ]

    _pop_varias(chaves_reset)
    limpar_mapeamento_widgets()

    if not manter_modelos:
        _pop_varias(
            [
                "df_modelo_cadastro",
                "modelo_cadastro_nome",
                "df_modelo_estoque",
                "modelo_estoque_nome",
                "modelo_cadastro_hash",
                "modelo_estoque_hash",
            ]
        )

    # 🔥 GARANTIA DE FLUXO
    st.session_state["etapa_origem"] = "origem"


def controlar_troca_operacao(operacao: str, log_debug) -> None:
    operacao_anterior = st.session_state.get("_operacao_anterior_origem_dados")

    if operacao_anterior is None:
        _set_if_changed("_operacao_anterior_origem_dados", operacao)
        return

    if operacao_anterior == operacao:
        return

    log_debug(
        f"Operação alterada de '{operacao_anterior}' para '{operacao}'. "
        "Resetando estados transitórios do fluxo."
    )

    resetar_estado_fluxo(manter_modelos=True)

    # 🔥 CORREÇÃO PRINCIPAL
    _set_if_changed("etapa_origem", "origem")

    _set_if_changed("_operacao_anterior_origem_dados", operacao)


def controlar_troca_origem(origem: str, log_debug) -> None:
    origem_anterior = st.session_state.get("_origem_anterior_origem_dados")

    if origem_anterior is None:
        _set_if_changed("_origem_anterior_origem_dados", origem)
        return

    if origem_anterior == origem:
        return

    log_debug(
        f"Origem alterada de '{origem_anterior}' para '{origem}'. "
        "Resetando estados transitórios do fluxo."
    )

    resetar_estado_fluxo(manter_modelos=True)

    # 🔥 CORREÇÃO PRINCIPAL
    _set_if_changed("etapa_origem", "origem")

    _set_if_changed("_origem_anterior_origem_dados", origem)


def sincronizar_estado_com_origem(df_origem, log_debug) -> None:
    if not safe_df_dados(df_origem):
        return

    novo_fingerprint = fingerprint_df(df_origem)
    fingerprint_atual = st.session_state.get("origem_dados_fingerprint", "")

    if fingerprint_atual != novo_fingerprint:
        log_debug("Nova origem detectada. Sincronizando estados do fluxo.")

        _set_if_changed("origem_dados_fingerprint", novo_fingerprint)
        st.session_state["df_origem"] = df_origem.copy()
        st.session_state["df_saida"] = df_origem.copy()
        st.session_state["df_final"] = df_origem.copy()

        st.session_state.pop("df_precificado", None)
        st.session_state["bloquear_campos_auto"] = {}

        st.session_state.pop("mapeamento_manual", None)
        st.session_state.pop("mapeamento_auto", None)
        st.session_state.pop("mapeamento_automatico", None)
        st.session_state.pop("mapeamento_colunas", None)
        st.session_state.pop("colunas_mapeadas", None)
        st.session_state.pop("df_mapeado", None)
        st.session_state.pop("mapeamento_manual_cadastro", None)
        st.session_state.pop("mapeamento_manual_estoque", None)

        limpar_mapeamento_widgets()
        return

    st.session_state["df_origem"] = df_origem.copy()

    if not safe_df_dados(st.session_state.get("df_saida")):
        st.session_state["df_saida"] = df_origem.copy()

    if not safe_df_dados(st.session_state.get("df_final")):
        st.session_state["df_final"] = st.session_state["df_saida"].copy()

    if "bloquear_campos_auto" not in st.session_state or not isinstance(
        st.session_state.get("bloquear_campos_auto"), dict
    ):
        st.session_state["bloquear_campos_auto"] = {}
