from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import (
    controlar_troca_operacao,
    garantir_estado_origem,
    safe_df_dados,
    safe_df_estrutura,
    set_etapa_origem,
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


def _obter_origem_atual() -> str:
    try:
        for key in ["origem_dados", "origem_selecionada", "tipo_origem", "origem"]:
            val = str(st.session_state.get(key) or "").strip().lower()
            if val:
                return val
        return ""
    except Exception:
        return ""


def _modelo_tem_estrutura(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_quantidade(valor, fallback: int) -> int:
    try:
        texto = str(valor or "").strip().lower()
        if texto in {"", "nan", "none"}:
            return int(fallback)

        if texto in {"sem estoque", "indisponível", "indisponivel", "zerado"}:
            return 0

        numero = int(float(str(valor).replace(",", ".")))
        return max(numero, 0)
    except Exception:
        return int(fallback)


def _sincronizar_tipo_operacao(operacao: str) -> None:
    try:
        controlar_troca_operacao(operacao, log_debug)
    except Exception:
        pass

    st.session_state["tipo_operacao_bling"] = (
        "cadastro" if operacao == "Cadastro de Produtos" else "estoque"
    )


def _sincronizar_df_saida_base(df_origem: pd.DataFrame) -> pd.DataFrame:
    try:
        modelo = obter_modelo_ativo()

        if isinstance(modelo, pd.DataFrame) and len(modelo.columns) > 0:
            precisa_recriar = True
            df_saida_existente = st.session_state.get("df_saida")

            if safe_df_estrutura(df_saida_existente):
                if list(df_saida_existente.columns) == list(modelo.columns):
                    precisa_recriar = False

            if precisa_recriar:
                df_saida = pd.DataFrame(index=range(len(df_origem)), columns=modelo.columns)
            else:
                df_saida = df_saida_existente.copy()
        else:
            df_saida = df_origem.copy()

        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
        return df_saida
    except Exception:
        df_saida = df_origem.copy()
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
        return df_saida


def _render_bloco_estoque(df_saida: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    try:
        df_saida = df_saida.copy()

        st.markdown("### Configurações de estoque")

        col1, col2 = st.columns(2)

        with col1:
            deposito = st.text_input(
                "Nome do depósito",
                value=str(st.session_state.get("deposito_nome", "") or ""),
                key="deposito_nome",
                placeholder="Ex.: ifood",
            )

        with col2:
            qtd_padrao = st.number_input(
                "Quantidade padrão",
                min_value=0,
                value=int(st.session_state.get("quantidade_fallback", 0) or 0),
                step=1,
                key="quantidade_fallback",
                help="Usado como fallback quando não houver quantidade válida.",
            )

        if deposito:
            if "Depósito" not in df_saida.columns:
                df_saida["Depósito"] = ""
            df_saida["Depósito"] = deposito

        if "Quantidade" not in df_saida.columns:
            df_saida["Quantidade"] = qtd_padrao

        if "site" in origem_atual:
            df_saida["Quantidade"] = df_saida["Quantidade"].apply(
                lambda v: _normalizar_quantidade(v, qtd_padrao)
            )

        return df_saida
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro bloco estoque: {e}", "ERRO")
        return df_saida


def _render_header_fluxo() -> None:
    st.subheader("Origem dos dados")
    st.caption("Carregue a origem, escolha a operação e o sistema aplica automaticamente o modelo interno do Bling.")


def _render_barra_etapas() -> None:
    etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()

    mapa = {
        "origem": "1. Origem",
        "mapeamento": "2. Mapeamento",
        "final": "3. Final",
        "envio": "4. Envio",
    }

    atual = mapa.get(etapa, "1. Origem")
    st.info(f"Etapa atual: {atual}")


def render_origem_dados() -> None:
    garantir_estado_origem()

    etapa = str(st.session_state.get("etapa", "origem") or "origem").strip().lower()

    _render_header_fluxo()
    _render_barra_etapas()

    if etapa == "mapeamento":
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            set_etapa_origem("origem")
            st.rerun()

    st.markdown("---")

    df_origem = render_origem_entrada()
    origem_atual = _obter_origem_atual()

    if "site" in origem_atual and not st.session_state.get("site_processado"):
        if not safe_df_dados(df_origem):
            st.info("Execute a busca do site para continuar.")
            return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    sincronizar_estado_com_origem(df_origem, log_debug)

    st.markdown("---")
    st.markdown("### Operação")

    operacao = st.radio(
        "Tipo de envio",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        key="tipo_operacao",
        horizontal=True,
    )
    _sincronizar_tipo_operacao(operacao)

    st.markdown("---")
    render_modelo_bling(operacao)

    modelo_ativo = obter_modelo_ativo()
    if not _modelo_tem_estrutura(modelo_ativo):
        st.warning("O modelo interno do Bling não está disponível.")
        return

    df_saida = _sincronizar_df_saida_base(df_origem)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        st.markdown("---")
        df_saida = _render_bloco_estoque(df_saida, origem_atual)
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()

    st.markdown("---")
    render_precificacao(df_origem)

    st.markdown("---")
    col1, col2 = st.columns([2, 1])

    with col1:
        st.caption("O mapeamento só avança quando origem, operação, base de saída e modelo interno estiverem válidos.")

    with col2:
        if st.button("➡️ Continuar para mapeamento", use_container_width=True):
            valido, erros = validar_antes_mapeamento()

            if not valido:
                for erro in erros:
                    st.warning(erro)
                return

            set_etapa_origem("mapeamento")
            st.rerun()
