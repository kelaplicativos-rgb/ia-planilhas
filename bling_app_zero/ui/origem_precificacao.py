
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import ir_para_etapa, log_debug, safe_df_dados
from bling_app_zero.ui.origem_dados_handlers import (
    aplicar_bloco_estoque,
    aplicar_precificacao,
    nome_coluna_preco_saida,
    safe_float,
    safe_str,
)


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _bool_state(key: str, default: bool = False) -> bool:
    try:
        return bool(st.session_state.get(key, default))
    except Exception:
        return default


def _tipo_operacao_estoque() -> bool:
    return safe_str(st.session_state.get("tipo_operacao_bling")).lower() == "estoque"


def _render_header() -> None:
    st.markdown("### Etapa de precificação")
    st.caption(
        "Escolha se vai usar a calculadora. Esta etapa não controla mais a navegação global "
        "sozinha; ela apenas prepara a saída para o mapeamento."
    )


def _colunas_origem_validas(df_origem: pd.DataFrame) -> list[str]:
    invalidas = {"signature", "infnfe", "infprot", "versao"}
    colunas: list[str] = []

    for coluna in df_origem.columns:
        nome = safe_str(coluna)
        if not nome:
            continue
        if nome.strip().lower() in invalidas:
            continue
        colunas.append(nome)

    return colunas


def _render_resumo(df_origem: pd.DataFrame) -> None:
    coluna_saida = nome_coluna_preco_saida()
    operacao = safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or st.session_state.get("tipo_operacao_radio")
    )

    st.info(
        f"Operação: {operacao or 'Não definida'} | "
        f"Linhas carregadas: {len(df_origem)} | "
        f"Coluna final automática: {coluna_saida}"
    )


def _render_escolha_principal() -> None:
    usar = _bool_state("usar_calculadora_precificacao", False)

    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "✅ Sim, vou precificar",
            use_container_width=True,
            type="primary" if usar else "secondary",
            key="btn_precificacao_sim",
        ):
            st.session_state["usar_calculadora_precificacao"] = True
            st.rerun()

    with col2:
        if st.button(
            "➡️ Não, manter preço da planilha",
            use_container_width=True,
            type="primary" if not usar else "secondary",
            key="btn_precificacao_nao",
        ):
            st.session_state["usar_calculadora_precificacao"] = False
            st.rerun()


def _render_form_calculadora(df_origem: pd.DataFrame) -> pd.DataFrame:
    colunas = _colunas_origem_validas(df_origem)
    coluna_preco_padrao = colunas[0] if colunas else ""

    coluna_custo = st.selectbox(
        "Qual coluna será usada como preço de custo/base?",
        options=colunas,
        index=colunas.index(st.session_state.get("precificacao_coluna_custo"))
        if st.session_state.get("precificacao_coluna_custo") in colunas
        else (0 if colunas else None),
        key="precificacao_coluna_custo",
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        margem = st.number_input("Margem lucro (%)", value=safe_float(st.session_state.get("margem_lucro"), 0.0), key="margem_lucro")
    with c2:
        impostos = st.number_input("Impostos (%)", value=safe_float(st.session_state.get("impostos"), 0.0), key="impostos")
    with c3:
        custo_fixo = st.number_input("Custo fixo", value=safe_float(st.session_state.get("custo_fixo"), 0.0), key="custo_fixo")
    with c4:
        taxa_extra = st.number_input("Taxa extra", value=safe_float(st.session_state.get("taxa_extra"), 0.0), key="taxa_extra")

    df_precificado = aplicar_precificacao(
        df_origem=df_origem,
        coluna_custo=coluna_custo or coluna_preco_padrao,
        margem_lucro=float(margem or 0.0),
        impostos=float(impostos or 0.0),
        custo_fixo=float(custo_fixo or 0.0),
        taxa_extra=float(taxa_extra or 0.0),
    )

    return df_precificado


def _aplicar_sem_calculadora(df_origem: pd.DataFrame) -> pd.DataFrame:
    df_out = _safe_copy_df(df_origem)
    coluna_saida = nome_coluna_preco_saida()

    if coluna_saida not in df_out.columns:
        df_out[coluna_saida] = ""

    return df_out


def _render_preview(df_saida: pd.DataFrame) -> None:
    with st.expander("Preview da precificação", expanded=False):
        st.dataframe(df_saida.head(5), use_container_width=True, hide_index=True)


def _persistir_saida(df_saida: pd.DataFrame) -> None:
    df_saida = aplicar_bloco_estoque(df_saida)

    st.session_state["df_precificado"] = df_saida.copy()
    st.session_state["df_calc_precificado"] = df_saida.copy()
    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()


def render_origem_precificacao(df_origem: pd.DataFrame | None = None) -> pd.DataFrame | None:
    df_base = df_origem if safe_df_dados(df_origem) else st.session_state.get("df_origem")

    if not safe_df_dados(df_base):
        st.warning("Carregue uma origem válida antes de usar a precificação.")
        return None

    _render_header()
    _render_resumo(df_base)
    _render_escolha_principal()

    usar_calculadora = _bool_state("usar_calculadora_precificacao", False)
    df_saida = _render_form_calculadora(df_base) if usar_calculadora else _aplicar_sem_calculadora(df_base)

    _persistir_saida(df_saida)
    _render_preview(df_saida)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para origem", use_container_width=True, key="btn_precificacao_voltar"):
            ir_para_etapa("origem")

    with col2:
        if st.button(
            "Continuar para mapeamento ➡️",
            use_container_width=True,
            key="btn_precificacao_continuar",
            type="primary",
        ):
            log_debug("[PRECIFICACAO] saída confirmada para mapeamento.", "INFO")
            ir_para_etapa("mapeamento")

    return df_saida
