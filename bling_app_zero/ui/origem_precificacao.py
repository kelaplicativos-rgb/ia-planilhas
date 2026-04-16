
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    formatar_numero_bling,
    log_debug,
    normalizar_coluna_busca,
    safe_df_dados,
    sincronizar_etapa_global,
    to_float_brasil,
)


# ============================================================
# HELPERS
# ============================================================


def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "nat"}:
        return ""
    return texto


def _set_etapa(etapa: str) -> None:
    st.session_state["fluxo_etapa"] = etapa
    try:
        sincronizar_etapa_global(etapa)
    except Exception:
        pass


def _voltar_para_modelo() -> None:
    _set_etapa("modelo")
    st.rerun()


def _ir_para_mapeamento() -> None:
    _set_etapa("mapeamento")
    st.rerun()


def _get_df_base() -> pd.DataFrame | None:
    """
    Prioridade nova:
    1) df_base_mapeamento
    2) df_origem
    3) fallbacks legados
    """
    for chave in [
        "df_base_mapeamento",
        "df_origem",
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
    ]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return None


def _coluna_operacional_preferida(df: pd.DataFrame) -> str:
    candidatos_preferidos = [
        "preco calculado",
        "preco base",
        "preco_base",
        "preco",
        "preco site",
        "preco_site",
        "valor",
        "valor unitario",
        "valor_unitario",
        "preço calculado",
        "preço base",
        "preço",
        "preço site",
        "preço unitário",
        "custo",
        "valor compra",
    ]

    mapa = {normalizar_coluna_busca(col): col for col in df.columns}

    for candidato in candidatos_preferidos:
        chave = normalizar_coluna_busca(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in df.columns:
        ncol = normalizar_coluna_busca(col)
        if any(token in ncol for token in ["preco", "preço", "valor", "custo"]):
            return col

    return ""


def _get_colunas_numericas(df: pd.DataFrame) -> list[str]:
    colunas_validas: list[str] = []

    for col in df.columns:
        try:
            serie = df[col].apply(to_float_brasil)
            serie_pd = pd.Series(serie)
            if serie_pd.notna().sum() > 0:
                colunas_validas.append(col)
        except Exception:
            continue

    return colunas_validas


def _calcular_preco(
    df: pd.DataFrame,
    coluna_base: str,
    margem: float,
    impostos: float,
    custo_fixo: float,
    taxa_extra: float,
) -> pd.DataFrame:
    df_calc = df.copy()
    base = df_calc[coluna_base].apply(to_float_brasil).fillna(0.0)

    fator = 1 + (float(margem) / 100.0) + (float(impostos) / 100.0)
    preco = (base * fator) + float(custo_fixo) + float(taxa_extra)

    df_calc["Preço calculado"] = preco.round(2)
    return df_calc


def _aplicar_preco_no_modelo(df: pd.DataFrame, tipo_operacao_bling: str) -> pd.DataFrame:
    df_out = df.copy()
    tipo = _safe_str(tipo_operacao_bling).lower()

    if "Preço calculado" not in df_out.columns:
        return df_out

    if tipo == "estoque":
        destino = "Preço unitário (OBRIGATÓRIO)"
    else:
        destino = "Preço de venda"

    if destino not in df_out.columns:
        df_out[destino] = ""

    df_out[destino] = df_out["Preço calculado"].apply(formatar_numero_bling)
    return df_out


def _manter_preco_original(df: pd.DataFrame, coluna_base: str, tipo_operacao_bling: str) -> pd.DataFrame:
    df_out = df.copy()
    tipo = _safe_str(tipo_operacao_bling).lower()

    df_out["Preço calculado"] = df_out[coluna_base].apply(to_float_brasil)

    if tipo == "estoque":
        destino = "Preço unitário (OBRIGATÓRIO)"
    else:
        destino = "Preço de venda"

    if destino not in df_out.columns:
        df_out[destino] = ""

    df_out[destino] = df_out["Preço calculado"].apply(formatar_numero_bling)
    return df_out


def _salvar_saida(df_calc: pd.DataFrame, df_final: pd.DataFrame) -> None:
    st.session_state["df_calc_precificado"] = df_calc.copy()
    st.session_state["df_origem_precificado"] = df_final.copy()
    st.session_state["df_precificado"] = df_final.copy()
    st.session_state["df_saida"] = df_final.copy()

    if not safe_df_dados(st.session_state.get("df_base_mapeamento")):
        st.session_state["df_base_mapeamento"] = df_final.copy()


def _render_preview_curto(df_final: pd.DataFrame) -> None:
    with st.expander("Preview da etapa", expanded=False):
        st.dataframe(df_final.head(20), use_container_width=True)


# ============================================================
# RENDER
# ============================================================


def render_origem_precificacao() -> None:
    st.markdown("### Precificação")
    st.caption("Escolha como o preço deve entrar no fluxo antes do mapeamento.")

    df_base = _get_df_base()

    if not safe_df_dados(df_base):
        st.warning("Ainda não existe base pronta para precificação.")
        if st.button("← Voltar para modelo", use_container_width=True):
            _voltar_para_modelo()
        return

    tipo_operacao_bling = _safe_str(st.session_state.get("tipo_operacao_bling", "cadastro")).lower()
    colunas_numericas = _get_colunas_numericas(df_base)

    if not colunas_numericas:
        st.warning("Nenhuma coluna numérica foi encontrada para usar como preço base.")
        if st.button("← Voltar para modelo", use_container_width=True):
            _voltar_para_modelo()
        return

    preferida = _coluna_operacional_preferida(df_base)
    default_idx = colunas_numericas.index(preferida) if preferida in colunas_numericas else 0

    with st.container(border=True):
        st.markdown("#### Como deseja precificar?")
        modo_precificacao = st.radio(
            "Escolha o modo",
            options=["Manter preço original", "Usar calculadora"],
            index=1 if bool(st.session_state.get("usar_calculadora_precificacao", True)) else 0,
            horizontal=False,
            key="modo_precificacao_radio",
        )

        usar_calculadora = modo_precificacao == "Usar calculadora"
        st.session_state["usar_calculadora_precificacao"] = usar_calculadora

    with st.container(border=True):
        st.markdown("#### Base do cálculo")
        coluna_base = st.selectbox(
            "Coluna de preço base",
            options=colunas_numericas,
            index=default_idx,
            key="precificacao_coluna_base",
        )

    if not usar_calculadora:
        df_calc = df_base.copy()
        df_final = _manter_preco_original(df_base, coluna_base, tipo_operacao_bling)
        _salvar_saida(df_calc, df_final)

        with st.container(border=True):
            st.success("O fluxo vai manter o preço original da base informada.")
            _render_preview_curto(df_final)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Voltar", use_container_width=True, key="voltar_precificacao_sem_calc"):
                _voltar_para_modelo()

        with col2:
            if st.button("Próximo →", use_container_width=True, key="continuar_precificacao_sem_calc"):
                log_debug("Precificação concluída mantendo preço original", "INFO")
                _ir_para_mapeamento()

        return

    with st.container(border=True):
        st.markdown("#### Calculadora")

        col1, col2 = st.columns(2)

        with col1:
            margem = st.number_input(
                "Margem (%)",
                min_value=0.0,
                value=float(st.session_state.get("precificacao_margem", 30.0)),
                step=1.0,
                key="precificacao_margem",
            )
            impostos = st.number_input(
                "Impostos (%)",
                min_value=0.0,
                value=float(st.session_state.get("precificacao_impostos", 10.0)),
                step=1.0,
                key="precificacao_impostos",
            )

        with col2:
            custo_fixo = st.number_input(
                "Custo fixo (R$)",
                min_value=0.0,
                value=float(st.session_state.get("precificacao_custo_fixo", 0.0)),
                step=1.0,
                key="precificacao_custo_fixo",
            )
            taxa_extra = st.number_input(
                "Taxa extra (R$)",
                min_value=0.0,
                value=float(st.session_state.get("precificacao_taxa_extra", 0.0)),
                step=1.0,
                key="precificacao_taxa_extra",
            )

    df_calc = _calcular_preco(
        df=df_base,
        coluna_base=coluna_base,
        margem=margem,
        impostos=impostos,
        custo_fixo=custo_fixo,
        taxa_extra=taxa_extra,
    )
    df_final = _aplicar_preco_no_modelo(df_calc, tipo_operacao_bling)
    _salvar_saida(df_calc, df_final)

    with st.container(border=True):
        st.markdown("#### Resultado")
        destino = "Preço unitário (OBRIGATÓRIO)" if tipo_operacao_bling == "estoque" else "Preço de venda"
        st.caption(f"O preço calculado já foi preparado para a coluna **{destino}**.")
        _render_preview_curto(df_final)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Voltar", use_container_width=True, key="voltar_precificacao"):
            _voltar_para_modelo()

    with col2:
        pode_avancar = safe_df_dados(df_final)
        if st.button(
            "Próximo →",
            use_container_width=True,
            disabled=not pode_avancar,
            key="continuar_precificacao",
        ):
            log_debug("Precificação aplicada com sucesso", "INFO")
            _ir_para_mapeamento()


