import streamlit as st

from bling_app_zero.core.precificacao import calcular_preco_venda
from bling_app_zero.utils.numeros import format_money


def render_precificacao_panel() -> None:
    st.subheader("Módulo de precificação")

    preco_compra_default = float(
        st.session_state.get("preco_compra_modulo_precificacao", 0.0) or 0.0
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        preco_compra = st.number_input(
            "Preço de compra",
            min_value=0.0,
            value=float(preco_compra_default),
            step=0.01,
            format="%.4f",
            key="preco_compra_ui",
        )

    with c2:
        percentual_impostos = st.number_input(
            "Impostos (%)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.4f",
        )

    with c3:
        margem_lucro = st.number_input(
            "Lucro (%)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.4f",
        )

    c4, c5 = st.columns(2)

    with c4:
        custo_fixo = st.number_input(
            "Custos fixos (R$)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.4f",
        )

    with c5:
        taxa_extra = st.number_input(
            "Taxas extras (%)",
            min_value=0.0,
            value=0.0,
            step=0.01,
            format="%.4f",
        )

    preco_venda = calcular_preco_venda(
        preco_compra=preco_compra,
        percentual_impostos=percentual_impostos,
        margem_lucro=margem_lucro,
        custo_fixo=custo_fixo,
        taxa_extra=taxa_extra,
    )

    st.metric("Preço de venda sugerido", format_money(preco_venda))

    origem_atual = st.session_state.get("origem_atual", "")
    if origem_atual == "XML NF-e":
        st.caption("Preço de compra preenchido automaticamente a partir do XML.")
