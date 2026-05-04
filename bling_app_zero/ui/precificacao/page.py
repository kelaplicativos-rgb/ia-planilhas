from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_core_flow import set_etapa_segura
from bling_app_zero.ui.app_helpers import safe_df_dados
from bling_app_zero.ui.precificacao.calc import calcular_preco, fmt_brl
from bling_app_zero.ui.precificacao.data import (
    aplicar_precificacao,
    coluna_preco_destino,
    obter_base,
    preparar_para_mapeamento,
)


def _voltar_para_origem() -> None:
    if set_etapa_segura("origem", origem="precificacao_voltar"):
        st.rerun()
    st.session_state["wizard_etapa_atual"] = "origem"
    st.session_state["etapa"] = "origem"
    st.rerun()


def _avancar(df: pd.DataFrame) -> None:
    if not safe_df_dados(df):
        st.error("Não foi possível preparar a planilha para o mapeamento.")
        return
    preparar_para_mapeamento(df)
    if set_etapa_segura("mapeamento", origem="precificacao_modular"):
        st.rerun()
    st.error("Não foi possível avançar para o mapeamento.")


def _valores_form() -> dict[str, float]:
    with st.container(border=True):
        st.markdown("### Despesas fixas por produto")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        c5, _ = st.columns(2)
        with c1:
            custo_fixo = st.number_input("Custo fixo adicional (R$)", min_value=0.0, step=0.01, key="pricing_custo_fixo")
        with c2:
            frete_fixo = st.number_input("Frete / custo logístico (R$)", min_value=0.0, step=0.01, key="pricing_frete_fixo")
        with c3:
            embalagem_fixa = st.number_input("Embalagem (R$)", min_value=0.0, step=0.01, key="pricing_embalagem_fixa")
        with c4:
            despesa_fixa = st.number_input("Outras despesas fixas (R$)", min_value=0.0, step=0.01, key="pricing_despesa_fixa")
        with c5:
            taxa_extra = st.number_input("Taxa extra fixa (R$)", min_value=0.0, step=0.01, key="pricing_taxa_extra")

    with st.container(border=True):
        st.markdown("### Percentuais sobre a venda")
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        c5, _ = st.columns(2)
        with c1:
            comissao_percent = st.number_input("Comissão marketplace (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_comissao_marketplace_percent")
        with c2:
            cartao_percent = st.number_input("Taxa cartão / financeira (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_taxa_cartao_percent")
        with c3:
            impostos_percent = st.number_input("Impostos (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_impostos_percent")
        with c4:
            lucro_percent = st.number_input("Lucro desejado (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_margem_percent")
        with c5:
            outros_percent = st.number_input("Outros percentuais (%)", min_value=0.0, max_value=99.99, step=0.01, key="pricing_outros_percent")

    return {
        "custo_fixo": custo_fixo,
        "frete_fixo": frete_fixo,
        "embalagem_fixa": embalagem_fixa,
        "despesa_fixa": despesa_fixa,
        "taxa_extra": taxa_extra,
        "comissao_percent": comissao_percent,
        "cartao_percent": cartao_percent,
        "impostos_percent": impostos_percent,
        "lucro_percent": lucro_percent,
        "outros_percent": outros_percent,
    }


def render_origem_precificacao() -> None:
    st.subheader("2. Precificação")
    df_base = obter_base()
    if not safe_df_dados(df_base):
        st.warning("A planilha de origem precisa estar carregada antes da precificação.")
        if st.button("⬅️ Voltar para origem", use_container_width=True, key="btn_voltar_prec_sem_dados"):
            _voltar_para_origem()
        return

    st.info("A precificação é opcional. Se não selecionar coluna base, o sistema segue com o preço já capturado.")
    colunas = [str(c) for c in df_base.columns]
    opcoes = [""] + colunas
    atual = st.session_state.get("pricing_coluna_custo", "")
    if atual not in opcoes:
        atual = ""

    with st.container(border=True):
        st.markdown("### Base de cálculo")
        coluna_custo = st.selectbox(
            "Coluna de custo/base",
            options=opcoes,
            index=opcoes.index(atual),
            key="pricing_coluna_custo",
            format_func=lambda v: "Não aplicar calculadora agora" if str(v).strip() == "" else str(v),
        )
        destino = coluna_preco_destino(df_base)
        st.caption(f"Destino do preço: {destino}")

    valores = _valores_form()
    percentual_total = sum(float(valores[k]) for k in ["comissao_percent", "cartao_percent", "impostos_percent", "lucro_percent", "outros_percent"])
    if percentual_total >= 100:
        st.error("A soma dos percentuais precisa ser menor que 100%.")

    with st.container(border=True):
        st.markdown("### Simulação")
        valor_teste = st.number_input("Valor de teste (R$)", min_value=0.0, step=0.01, key="pricing_valor_teste")
        st.success(f"Preço calculado: {fmt_brl(calcular_preco(valor_teste, valores))}")

    if st.button("Aplicar precificação", use_container_width=True, key="btn_aplicar_precificacao"):
        if percentual_total >= 100:
            st.error("Não é possível aplicar: percentuais acima do limite.")
        elif not coluna_custo:
            st.session_state["pricing_df_preview"] = df_base.copy()
            preparar_para_mapeamento(df_base)
            st.info("Calculadora não aplicada. O fluxo seguirá com o preço já existente.")
        else:
            df_aplicado = aplicar_precificacao(df_base, coluna_custo, valores)
            st.session_state["pricing_df_preview"] = df_aplicado.copy()
            preparar_para_mapeamento(df_aplicado)
            st.success("Precificação aplicada com sucesso.")

    df_preview = st.session_state.get("pricing_df_preview")
    if not safe_df_dados(df_preview):
        df_preview = df_base.copy()
    st.markdown("### Preview da planilha atual")
    st.dataframe(df_preview.head(80), use_container_width=True)

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ Voltar para origem", use_container_width=True, key="btn_voltar_precificacao"):
            _voltar_para_origem()
    with c2:
        if st.button("Continuar ➜", use_container_width=True, key="btn_continuar_precificacao"):
            _avancar(df_preview)
