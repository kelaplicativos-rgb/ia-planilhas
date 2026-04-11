from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import (
    controlar_troca_operacao,
    controlar_troca_origem,
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
from bling_app_zero.ui.origem_saida import (
    obter_df_base_prioritaria,
)


# ==========================================================
# HELPERS
# ==========================================================
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


def _garantir_coluna(df: pd.DataFrame, nome: str, valor_padrao="") -> pd.DataFrame:
    try:
        if nome not in df.columns:
            df[nome] = valor_padrao
        return df
    except Exception:
        return df


def _aplicar_bloco_estoque(df_saida: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    try:
        df_saida = df_saida.copy()

        st.markdown("### Dados de estoque")

        deposito = st.text_input(
            "Nome do depósito",
            value=str(st.session_state.get("deposito_nome", "") or ""),
            key="deposito_nome",
            placeholder="Ex.: ifood",
        )

        qtd = st.number_input(
            "Quantidade padrão",
            min_value=0,
            value=int(st.session_state.get("quantidade_fallback", 0) or 0),
            step=1,
            key="quantidade_fallback",
            help="Usado como fallback quando não houver quantidade válida.",
        )

        if deposito:
            df_saida = _garantir_coluna(df_saida, "Depósito", "")
            df_saida["Depósito"] = deposito

        df_saida = _garantir_coluna(df_saida, "Quantidade", qtd)

        if "site" in origem_atual:
            df_saida["Quantidade"] = df_saida["Quantidade"].apply(
                lambda v: _normalizar_quantidade(v, qtd)
            )
        else:
            df_saida["Quantidade"] = df_saida["Quantidade"].fillna(qtd)

        return df_saida

    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro bloco estoque: {e}", "ERROR")
        return df_saida


def _render_header_fluxo() -> None:
    st.subheader("Origem dos dados")
    st.caption(
        "Carregue a origem, escolha a operação e o sistema aplica automaticamente o modelo do Bling."
    )


# ==========================================================
# RENDER
# ==========================================================
def render_origem_dados() -> None:
    garantir_estado_origem()
    _render_header_fluxo()

    etapa = str(st.session_state.get("etapa_origem", "origem") or "origem").strip().lower()

    if etapa == "mapeamento":
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            set_etapa_origem("origem")
            st.rerun()
        return

    df_origem = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )

    origem_atual = _obter_origem_atual()

    if "site" in origem_atual and not st.session_state.get("site_processado"):
        if not safe_df_dados(df_origem):
            st.info("Execute a busca do site para continuar.")
            return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    st.session_state["df_origem"] = df_origem.copy()
    sincronizar_estado_com_origem(df_origem, log_debug)

    st.markdown("---")

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
        st.warning("⚠️ Modelo do Bling não encontrado.")
        return

    df_saida = obter_df_base_prioritaria(df_origem, origem_atual)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        df_saida = _aplicar_bloco_estoque(df_saida, origem_atual)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    st.markdown("---")

    render_precificacao(df_origem)

    df_prec = st.session_state.get("df_calc_precificado")
    if safe_df_estrutura(df_prec):
        st.session_state["df_precificado"] = df_prec.copy()

    st.markdown("---")

    if st.button("➡️ Continuar para mapeamento", use_container_width=True, type="primary"):
        valido, erros = validar_antes_mapeamento()

        if not valido:
            for erro in erros:
                st.warning(erro)
            return

        if safe_df_estrutura(st.session_state.get("df_saida")):
            st.session_state["df_final"] = st.session_state["df_saida"].copy()

        set_etapa_origem("mapeamento")
        st.rerun()
