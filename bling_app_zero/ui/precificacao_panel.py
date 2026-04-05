import streamlit as st


def calcular_preco_venda(
    custo: float,
    margem: float,
    taxa_percentual: float,
    custo_fixo: float,
) -> float:
    """
    Fórmula padrão:
    Preço venda = (custo + custo fixo) / (1 - margem - taxa)
    """
    try:
        margem = margem / 100
        taxa = taxa_percentual / 100

        denominador = 1 - margem - taxa

        if denominador <= 0:
            return 0.0

        return (custo + custo_fixo) / denominador
    except Exception:
        return 0.0


def render_precificacao_panel() -> None:
    st.subheader("Definição de preço (IA)")

    preco_compra = float(
        st.session_state.get("preco_compra_modulo_precificacao", 0.0)
    )

    st.info(f"Preço de custo detectado: R$ {preco_compra:.2f}")

    col1, col2, col3 = st.columns(3)

    with col1:
        margem = st.number_input(
            "Lucro (%)",
            min_value=0.0,
            max_value=100.0,
            value=30.0,
            step=1.0,
        )

    with col2:
        taxa = st.number_input(
            "Taxas (%)",
            min_value=0.0,
            max_value=100.0,
            value=15.0,
            step=1.0,
        )

    with col3:
        custo_fixo = st.number_input(
            "Custos fixos (R$)",
            min_value=0.0,
            value=0.0,
            step=1.0,
        )

    preco_venda = calcular_preco_venda(
        custo=preco_compra,
        margem=margem,
        taxa_percentual=taxa,
        custo_fixo=custo_fixo,
    )

    st.session_state["preco_venda_calculado"] = preco_venda

    st.markdown("---")

    colA, colB = st.columns(2)

    with colA:
        st.metric("Preço de custo", f"R$ {preco_compra:.2f}")

    with colB:
        st.metric("Preço de venda sugerido", f"R$ {preco_venda:.2f}")

    if preco_venda <= 0:
        st.warning(
            "A soma de margem + taxas está inválida (≥100%). "
            "Ajuste os valores."
        )
