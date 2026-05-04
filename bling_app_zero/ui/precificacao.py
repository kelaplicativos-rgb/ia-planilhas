from __future__ import annotations

import streamlit as st


def _avancar() -> None:
    st.session_state["wizard_etapa_atual"] = "mapeamento"
    st.session_state["wizard_etapa_maxima"] = "mapeamento"
    st.rerun()


def _voltar() -> None:
    st.session_state["wizard_etapa_atual"] = "origem"
    st.rerun()


def render_origem_precificacao() -> None:
    st.title("2. Precificação")
    st.info("Etapa de precificação carregada com segurança. Você pode seguir sem cálculo ou usar os campos abaixo como base.")

    usar = st.checkbox("Usar cálculo simples de preço", value=st.session_state.get("usar_precificacao", False))
    st.session_state["usar_precificacao"] = usar

    if usar:
        custo = st.number_input("Custo base", min_value=0.0, value=float(st.session_state.get("preco_custo_base", 0.0)), step=1.0)
        lucro = st.number_input("Lucro desejado (%)", min_value=0.0, value=float(st.session_state.get("lucro_percentual", 30.0)), step=1.0)
        taxas = st.number_input("Taxas/despesas (%)", min_value=0.0, value=float(st.session_state.get("taxas_percentual", 0.0)), step=1.0)
        preco = custo * (1 + (lucro + taxas) / 100)
        st.session_state["preco_custo_base"] = custo
        st.session_state["lucro_percentual"] = lucro
        st.session_state["taxas_percentual"] = taxas
        st.session_state["preco_unitario_calculado"] = round(preco, 2)
        st.success(f"Preço calculado: R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    else:
        st.caption("Sem precificação automática: o preço virá da planilha/origem no mapeamento.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            _voltar()
    with col2:
        if st.button("Avançar para mapeamento ➡️", use_container_width=True):
            _avancar()
