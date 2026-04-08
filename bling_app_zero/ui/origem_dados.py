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


def _sincronizar_df_saida_base(df_origem: pd.DataFrame) -> pd.DataFrame:
    try:
        df_saida = st.session_state.get("df_saida")

        if not safe_df_dados(df_saida):
            df_saida = df_origem.copy()
            st.session_state["df_saida"] = df_saida.copy()

        st.session_state["df_final"] = df_saida.copy()
        return df_saida
    except Exception:
        df_saida = df_origem.copy()
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
        return df_saida


def _garantir_coluna(df: pd.DataFrame, coluna: str, valor_padrao="") -> pd.DataFrame:
    try:
        if coluna not in df.columns:
            df[coluna] = valor_padrao
        return df
    except Exception:
        return df


def _normalizar_quantidade(valor, fallback: int) -> int:
    try:
        texto = str(valor or "").strip().lower()

        if texto in {"", "nan", "none", "<na>"}:
            return int(fallback)

        if texto in {"sem estoque", "indisponível", "indisponivel", "zerado"}:
            return 0

        numero = int(float(str(valor).replace(",", ".")))
        if numero < 0:
            return 0

        return numero
    except Exception:
        return int(fallback)


def _aplicar_bloco_estoque(df_saida: pd.DataFrame, origem_atual: str) -> pd.DataFrame:
    try:
        df_saida = df_saida.copy()

        st.markdown("### 🏬 Dados de estoque")

        deposito_atual = str(st.session_state.get("deposito_nome", "") or "").strip()
        deposito = st.text_input(
            "Nome do depósito",
            value=deposito_atual,
            key="deposito_nome",
            placeholder="Ex.: ifood",
        )

        if deposito:
            df_saida = _garantir_coluna(df_saida, "Depósito", "")
            df_saida["Depósito"] = deposito

        if "site" in origem_atual:
            qtd = st.number_input(
                "Quantidade padrão",
                min_value=0,
                value=int(st.session_state.get("quantidade_fallback", 0) or 0),
                step=1,
                key="quantidade_fallback",
                help="Só usada quando a origem vier do site e alguma quantidade estiver vazia.",
            )

            df_saida = _garantir_coluna(df_saida, "Quantidade", qtd)
            df_saida["Quantidade"] = df_saida["Quantidade"].apply(
                lambda v: _normalizar_quantidade(v, qtd)
            )
        else:
            if "Quantidade" in df_saida.columns:
                try:
                    df_saida["Quantidade"] = df_saida["Quantidade"].apply(
                        lambda v: _normalizar_quantidade(v, 0)
                    )
                except Exception:
                    pass

        return df_saida
    except Exception as e:
        log_debug(f"[ORIGEM_DADOS] erro bloco estoque: {e}", "ERROR")
        return df_saida


def render_origem_dados() -> None:
    etapa = st.session_state.get("etapa_origem")
    if etapa in ["mapeamento", "final"]:
        return

    st.subheader("📦 Origem dos dados")

    # =========================================================
    # 1) ORIGEM
    # =========================================================
    df_origem = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )

    origem_atual = _obter_origem_atual()

    # 🔒 TRAVA PARA SITE
    if "site" in origem_atual and not st.session_state.get("site_processado"):
        st.info("🔎 Execute a busca do site para continuar.")
        return

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    sincronizar_estado_com_origem(df_origem, log_debug)

    st.markdown("---")

    # =========================================================
    # 2) TIPO DE ENVIO
    # =========================================================
    st.markdown("### Tipo de envio")

    operacao_inicial = _obter_operacao_atual_label()

    if "tipo_operacao" not in st.session_state:
        st.session_state["tipo_operacao"] = operacao_inicial

    operacao = st.radio(
        "Selecione",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        key="tipo_operacao",
        horizontal=False,
        label_visibility="collapsed",
    )

    _sincronizar_tipo_operacao(operacao)

    st.markdown("---")

    # =========================================================
    # 3) MODELO BLING
    # =========================================================
    st.markdown("### Modelo Bling")
    render_modelo_bling(operacao)

    modelo_ok = safe_df_dados(obter_modelo_ativo())
    if not modelo_ok:
        st.warning("⚠️ Anexe o modelo do Bling para continuar.")
        return

    # =========================================================
    # 4) PREPARAÇÃO DF SAÍDA
    # =========================================================
    df_saida = _sincronizar_df_saida_base(df_origem)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        df_saida = _aplicar_bloco_estoque(df_saida, origem_atual)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    st.markdown("---")

    # =========================================================
    # 5) PRECIFICAÇÃO
    # =========================================================
    st.markdown("### 💰 Precificação")
    render_precificacao(df_origem)

    st.markdown("---")

    # =========================================================
    # 6) CONTINUAR
    # =========================================================
    if st.button(
        "➡️ Continuar para mapeamento",
        use_container_width=True,
    ):
        valido, erros = validar_antes_mapeamento()

        if not valido:
            for e in erros:
                st.warning(e)
            return

        st.session_state["etapa_origem"] = "mapeamento"
        st.rerun()
