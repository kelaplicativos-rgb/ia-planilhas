from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import (
    controlar_troca_operacao,
    controlar_troca_origem,
    safe_df_dados,
    sincronizar_estado_com_origem,
)
from bling_app_zero.ui.origem_dados_precificacao import render_precificacao
from bling_app_zero.ui.origem_dados_uploads import (
    render_modelo_bling,
    render_origem_entrada,
)
from bling_app_zero.ui.origem_dados_validacao import (
    obter_modelo_ativo,
    validar_antes_mapeamento,
)


ETAPAS_VALIDAS_ORIGEM = {"origem", "mapeamento", "final"}


def _obter_origem_atual() -> str:
    try:
        for key in ["origem_dados", "origem_selecionada", "tipo_origem", "origem"]:
            val = str(st.session_state.get(key) or "").strip().lower()
            if val:
                return val
        return ""
    except Exception:
        return ""


def _obter_operacao_atual_label() -> str:
    try:
        valor = str(st.session_state.get("tipo_operacao") or "").strip()
        if valor in ["Cadastro de Produtos", "Atualização de Estoque"]:
            return valor

        tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()
        if tipo == "estoque":
            return "Atualização de Estoque"

        return "Cadastro de Produtos"
    except Exception:
        return "Cadastro de Produtos"


def _sincronizar_tipo_operacao(operacao: str) -> None:
    try:
        controlar_troca_operacao(operacao, log_debug)
    except Exception:
        pass

    st.session_state["tipo_operacao_bling"] = (
        "cadastro" if operacao == "Cadastro de Produtos" else "estoque"
    )


def _normalizar_etapa_origem() -> str:
    try:
        etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()

        if etapa not in ETAPAS_VALIDAS_ORIGEM:
            log_debug(f"Etapa desconhecida: {etapa}", "ERROR")
            st.session_state["etapa_origem"] = "origem"
            return "origem"

        st.session_state["etapa_origem"] = etapa
        return etapa
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao normalizar etapa: {e}", "ERROR")
        st.session_state["etapa_origem"] = "origem"
        return "origem"


def _sincronizar_df_saida_base(df_origem: pd.DataFrame) -> pd.DataFrame:
    try:
        if safe_df_dados(st.session_state.get("df_saida")):
            return st.session_state["df_saida"]

        df_saida = df_origem.copy()
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
        return df_saida

    except Exception:
        df_saida = df_origem.copy()
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
        return df_saida


def _modelo_tem_estrutura(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


# =========================================================
# RENDER
# =========================================================
def render_origem_dados() -> None:
    etapa = _normalizar_etapa_origem()

    st.subheader("📦 Origem dos dados")

    # 🔥 NÃO EXISTE MAIS etapa final aqui

    if etapa == "mapeamento":
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            st.session_state["etapa_origem"] = "origem"
            st.rerun()

    df_origem = render_origem_entrada()

    origem_atual = _obter_origem_atual()

    if "site" in origem_atual and not st.session_state.get("site_processado"):
        st.info("🔎 Execute a busca do site para continuar.")
        return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    try:
        sincronizar_estado_com_origem(df_origem, log_debug)
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro ao sincronizar estado com origem: {e}", "ERROR")

    etapa = _normalizar_etapa_origem()

    st.markdown("---")

    operacao_padrao = _obter_operacao_atual_label()
    opcoes_operacao = ["Cadastro de Produtos", "Atualização de Estoque"]

    if operacao_padrao not in opcoes_operacao:
        operacao_padrao = "Cadastro de Produtos"

    operacao = st.radio(
        "Tipo de envio",
        opcoes_operacao,
        key="tipo_operacao",
        index=opcoes_operacao.index(operacao_padrao),
    )

    _sincronizar_tipo_operacao(operacao)

    st.markdown("---")

    render_modelo_bling(operacao)

    if not _modelo_tem_estrutura(obter_modelo_ativo()):
        st.warning("⚠️ Anexe o modelo do Bling para continuar.")
        return

    df_saida = _sincronizar_df_saida_base(df_origem)

    st.session_state["df_saida"] = df_saida.copy()

    st.markdown("---")

    render_precificacao(df_origem)

    st.markdown("---")

    if etapa == "origem":
        if st.button("➡️ Continuar para mapeamento", use_container_width=True):
            valido, erros = validar_antes_mapeamento()

            if not valido:
                for erro in erros:
                    st.warning(erro)
                return

            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()
