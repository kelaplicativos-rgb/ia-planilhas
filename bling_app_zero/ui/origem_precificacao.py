
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_handlers import (
    aplicar_bloco_estoque,
    aplicar_precificacao,
    nome_coluna_preco_saida,
)


# =========================================================
# HELPERS LOCAIS
# =========================================================
def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _safe_df_dados(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _float_state(key: str, default: float = 0.0) -> float:
    try:
        return float(st.session_state.get(key, default) or default)
    except Exception:
        return default


def _bool_state(key: str, default: bool = False) -> bool:
    try:
        return bool(st.session_state.get(key, default))
    except Exception:
        return default


def _set_etapa(destino: str) -> None:
    st.session_state["etapa_origem"] = destino
    st.session_state["etapa"] = destino
    st.session_state["etapa_fluxo"] = destino


def _navegar(destino: str) -> None:
    _set_etapa(destino)
    st.rerun()


def _tipo_operacao_estoque() -> bool:
    return _safe_str(st.session_state.get("tipo_operacao_bling")).lower() == "estoque"


def _origem_atual() -> str:
    return _safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
    ).lower()


# =========================================================
# CSS / CABEÇALHO
# =========================================================
def _render_css() -> None:
    st.markdown(
        """
        <style>
            .op-kicker {
                font-size: 0.84rem;
                color: #667085;
                font-weight: 700;
                margin-bottom: 0.30rem;
            }

            .op-title {
                font-size: 2rem;
                line-height: 1.05;
                color: #0A2259;
                font-weight: 800;
                margin: 0 0 0.40rem 0;
                letter-spacing: -0.02em;
            }

            .op-sub {
                font-size: 1rem;
                color: #667085;
                margin: 0 0 1rem 0;
            }

            .op-card {
                background: #FFFFFF;
                border: 1px solid #EAECF0;
                border-radius: 20px;
                padding: 0.95rem 1rem;
                margin: 0.75rem 0 1rem 0;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header() -> None:
    st.markdown('<div class="op-kicker">Etapa de precificação</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="op-title">Vai usar a calculadora de precificação?</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="op-sub">Você pode calcular automaticamente ou manter o preço que veio da planilha fornecedora.</div>',
        unsafe_allow_html=True,
    )


# =========================================================
# UI
# =========================================================
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


def _colunas_origem_validas(df_origem: pd.DataFrame) -> list[str]:
    invalidas = {"signature", "infnfe", "infprot", "versao"}

    colunas: list[str] = []
    for coluna in df_origem.columns:
        nome = _safe_str(coluna)
        if not nome:
            continue
        if nome.strip().lower() in invalidas:
            continue
        colunas.append(nome)

    return colunas


def _render_resumo(df_origem: pd.DataFrame) -> None:
    coluna_saida = nome_coluna_preco_saida()
    operacao = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_bling")
        or st.session_state.get("tipo_operacao_radio")
    )

    st.markdown(
        f"""
        <div class="op-card">
            <strong>Operação:</strong> {operacao or "Não definida"}<br/>
            <strong>Linhas carregadas:</strong> {len(df_origem)}<br/>
            <strong>Coluna final automática:</strong> {coluna_saida}
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# APLICAÇÃO DA PRECIFICAÇÃO
# =========================================================
def _persistir_resultado(df_resultado: pd.DataFrame) -> None:
    st.session_state["df_precificado"] = _safe_copy_df(df_resultado)
    st.session_state["df_calc_precificado"] = _safe_copy_df(df_resultado)
    st.session_state["df_saida"] = _safe_copy_df(df_resultado)
    st.session_state["df_final"] = _safe_copy_df(df_resultado)


def _aplicar_precificacao_fluxo(df_origem: pd.DataFrame) -> None:
    usar = _bool_state("usar_calculadora_precificacao", False)

    coluna_base = _safe_str(st.session_state.get("coluna_precificacao_resultado"))
    margem = _float_state("margem_bling", 0.0)
    impostos = _float_state("impostos_bling", 0.0)
    frete_estimado = _float_state("custofixo_bling", 0.0)
    custo_extra = _float_state("taxaextra_bling", 0.0)
    comissao_canal = _float_state("comissao_canal_percentual", 16.0)

    st.session_state["usar_calculadora_precificacao"] = usar
    st.session_state["comissao_canal_percentual"] = comissao_canal

    df_resultado = aplicar_precificacao(
        df_origem=df_origem,
        coluna_custo=coluna_base,
        margem=margem,
        impostos=impostos,
        custo_fixo=frete_estimado,
        taxa_extra=custo_extra,
    )

    if _safe_df_dados(df_resultado):
        if _tipo_operacao_estoque():
            df_resultado = aplicar_bloco_estoque(df_resultado, _origem_atual())

        _persistir_resultado(df_resultado)


# =========================================================
# RENDER PRINCIPAL
# =========================================================
def render_origem_precificacao() -> None:
    _render_css()

    df_origem = st.session_state.get("df_origem")
    if not _safe_df_dados(df_origem):
        st.warning("Carregue a base de origem antes de usar a etapa de precificação.")

        col1, col2 = st.columns(2, gap="small")
        with col1:
            if st.button(
                "⬅️ Voltar para origem",
                use_container_width=True,
                key="prec_sem_base_voltar",
            ):
                _navegar("origem")
        with col2:
            st.button(
                "Continuar ➜",
                use_container_width=True,
                disabled=True,
                key="prec_sem_base_continuar",
            )
        return

    _render_header()
    _render_escolha_principal()
    _render_resumo(df_origem)

    usar = _bool_state("usar_calculadora_precificacao", False)

    if not usar:
        _aplicar_precificacao_fluxo(df_origem)
        st.success(
            f"O sistema vai manter o preço da planilha fornecedora e preencher a coluna final {nome_coluna_preco_saida()}."
        )

        col1, col2 = st.columns(2, gap="small")
        with col1:
            if st.button("⬅️ Voltar", use_container_width=True, key="prec_nao_voltar"):
                _navegar("origem")
        with col2:
            if st.button(
                "Continuar ➜",
                use_container_width=True,
                type="primary",
                key="prec_nao_continuar",
            ):
                _navegar("mapeamento")
        return

    opcoes = [""] + _colunas_origem_validas(df_origem)

    st.selectbox(
        "Qual coluna de origem deve ser usada como base do preço?",
        opcoes,
        key="coluna_precificacao_resultado",
    )

    col1, col2 = st.columns(2, gap="small")

    with col1:
        st.number_input(
            "Margem desejada (%)",
            min_value=0.0,
            value=_float_state("margem_bling", 0.0),
            step=1.0,
            key="margem_bling",
        )
        st.number_input(
            "Imposto NF-e (%)",
            min_value=0.0,
            value=_float_state("impostos_bling", 0.0),
            step=1.0,
            key="impostos_bling",
        )
        st.number_input(
            "Comissão do canal (%)",
            min_value=0.0,
            value=_float_state("comissao_canal_percentual", 16.0),
            step=1.0,
            key="comissao_canal_percentual",
        )

    with col2:
        st.number_input(
            "Frete estimado (R$)",
            min_value=0.0,
            value=_float_state("custofixo_bling", 0.0),
            step=1.0,
            key="custofixo_bling",
        )
        st.number_input(
            "Custo extra fixo (R$)",
            min_value=0.0,
            value=_float_state("taxaextra_bling", 0.0),
            step=1.0,
            key="taxaextra_bling",
        )

    _aplicar_precificacao_fluxo(df_origem)

    coluna_saida = nome_coluna_preco_saida()
    st.success(f"O resultado da calculadora será gravado automaticamente em: {coluna_saida}")

    with st.expander("Abrir preview após precificação", expanded=False):
        df_preview = st.session_state.get("df_precificado")
        if _safe_df_dados(df_preview):
            st.dataframe(df_preview.head(20), use_container_width=True)

    col1, col2 = st.columns(2, gap="small")
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True, key="prec_sim_voltar"):
            _navegar("origem")
    with col2:
        if st.button(
            "Continuar ➜",
            use_container_width=True,
            type="primary",
            key="prec_sim_continuar",
        ):
            _navegar("mapeamento")
