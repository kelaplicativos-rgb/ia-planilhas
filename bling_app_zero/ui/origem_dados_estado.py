from __future__ import annotations

import hashlib

import streamlit as st


def safe_df_dados(df) -> bool:
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


def fingerprint_df(df) -> str:
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


def resetar_estado_fluxo(manter_modelos: bool = True) -> None:
    chaves_reset = [
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "bloquear_campos_auto",
        "mapeamento_automatico",
        "mapeamento_manual",
        "mapeamento_manual_cadastro",
        "mapeamento_manual_estoque",
        "coluna_preco_base",
        "origem_dados_fingerprint",
        "df_origem_site",
        "df_origem_xml",
        "arquivo_origem_hash",
        "arquivo_origem_nome",
    ]

    for chave in chaves_reset:
        st.session_state.pop(chave, None)

    limpar_mapeamento_widgets()

    if not manter_modelos:
        st.session_state.pop("df_modelo_cadastro", None)
        st.session_state.pop("modelo_cadastro_nome", None)
        st.session_state.pop("df_modelo_estoque", None)
        st.session_state.pop("modelo_estoque_nome", None)
        st.session_state.pop("modelo_cadastro_hash", None)
        st.session_state.pop("modelo_estoque_hash", None)


def controlar_troca_operacao(operacao: str, log_debug) -> None:
    operacao_anterior = st.session_state.get("_operacao_anterior_origem_dados")

    if operacao_anterior is None:
        st.session_state["_operacao_anterior_origem_dados"] = operacao
        return

    if operacao_anterior != operacao:
        log_debug(
            f"Operação alterada de '{operacao_anterior}' para '{operacao}'. "
            "Resetando estados transitórios do fluxo."
        )

        resetar_estado_fluxo(manter_modelos=True)

        if not tem_upload_ativo():
            st.session_state["etapa_origem"] = "upload"

        st.session_state["_operacao_anterior_origem_dados"] = operacao


def controlar_troca_origem(origem: str, log_debug) -> None:
    origem_anterior = st.session_state.get("_origem_anterior_origem_dados")

    if origem_anterior is None:
        st.session_state["_origem_anterior_origem_dados"] = origem
        return

    if origem_anterior != origem:
        log_debug(
            f"Origem alterada de '{origem_anterior}' para '{origem}'. "
            "Resetando estados transitórios do fluxo."
        )

        resetar_estado_fluxo(manter_modelos=True)

        if not tem_upload_ativo():
            st.session_state["etapa_origem"] = "upload"

        st.session_state["_origem_anterior_origem_dados"] = origem


def sincronizar_estado_com_origem(df_origem, log_debug) -> None:
    if not safe_df_dados(df_origem):
        return

    novo_fingerprint = fingerprint_df(df_origem)
    fingerprint_atual = st.session_state.get("origem_dados_fingerprint", "")

    if fingerprint_atual != novo_fingerprint:
        log_debug("Nova origem detectada. Sincronizando estados do fluxo.")
        st.session_state["origem_dados_fingerprint"] = novo_fingerprint
        st.session_state["df_origem"] = df_origem.copy()
        st.session_state["df_saida"] = df_origem.copy()
        st.session_state["df_final"] = df_origem.copy()
        st.session_state.pop("df_precificado", None)
        st.session_state["bloquear_campos_auto"] = {}
        st.session_state.pop("mapeamento_manual_cadastro", None)
        st.session_state.pop("mapeamento_manual_estoque", None)
        limpar_mapeamento_widgets()
    else:
        st.session_state["df_origem"] = df_origem.copy()

        if not safe_df_dados(st.session_state.get("df_saida")):
            st.session_state["df_saida"] = df_origem.copy()

        if not safe_df_dados(st.session_state.get("df_final")):
            st.session_state["df_final"] = st.session_state["df_saida"].copy()
