from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.product_pipeline import build_product_master, choose_best_source_df
from bling_app_zero.core.product_validator import get_validation_summary


def _metric_card(label: str, value: int | float | str, help_text: str = "") -> None:
    st.metric(label=label, value=value, help=help_text or None)


def _get_default_origem() -> str:
    for key in ["origem_dados_tipo", "origem_tipo", "tipo_origem", "origem"]:
        value = st.session_state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Fluxo atual"


def _get_default_deposito() -> str:
    for key in ["deposito_nome", "nome_deposito", "deposito", "deposito_manual"]:
        value = st.session_state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def render_hub_dashboard() -> None:
    st.subheader("🧠 BLINGHUB — Produto Mestre")
    st.caption("Central inspirada em Hub/ERP: qualquer origem entra, o sistema normaliza, valida e prepara para Bling/marketplaces.")

    source_df = choose_best_source_df(st.session_state)
    if source_df.empty:
        st.info("Nenhuma base de produtos encontrada ainda. Comece pela etapa Origem para carregar planilha, XML, PDF ou captura por site.")
        return

    with st.expander("⚙️ Configuração rápida do Hub", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            origem = st.text_input("Origem", value=_get_default_origem(), key="hub_origem")
        with col2:
            fornecedor = st.text_input("Fornecedor", value=str(st.session_state.get("hub_fornecedor", "") or ""), key="hub_fornecedor")
        with col3:
            deposito = st.text_input("Depósito", value=_get_default_deposito(), key="hub_deposito")

        preco_calculado_col = st.selectbox(
            "Coluna de preço calculado (opcional)",
            options=[""] + [str(c) for c in source_df.columns],
            index=0,
            key="hub_preco_calculado_col",
        )

    master = build_product_master(
        df=source_df,
        origem=origem,
        fornecedor=fornecedor,
        deposito=deposito,
        preco_calculado_col=preco_calculado_col or None,
    )
    st.session_state["df_product_master"] = master

    summary = get_validation_summary(master)
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        _metric_card("Produtos", summary["total"])
    with col2:
        _metric_card("OK", summary["ok"])
    with col3:
        _metric_card("Revisar", summary["revisar"])
    with col4:
        _metric_card("Sem descrição", summary["sem_descricao"])
    with col5:
        _metric_card("Sem preço", summary["sem_preco"])
    with col6:
        _metric_card("GTIN inválido", summary["gtin_invalidos"])

    if summary["revisar"]:
        st.warning("Existem produtos que precisam de revisão antes do envio/exportação final.")
    else:
        st.success("Produto Mestre validado sem alertas críticos.")

    with st.expander("📦 Produto Mestre normalizado", expanded=True):
        st.dataframe(master, use_container_width=True, height=420)

    revisar = master[master.get("status_validacao") == "revisar"] if "status_validacao" in master.columns else pd.DataFrame()
    if not revisar.empty:
        with st.expander("⚠️ Itens para revisar", expanded=False):
            st.dataframe(revisar, use_container_width=True, height=300)

    st.caption("Este Hub ainda não substitui o Preview Final. Ele cria uma base mestre segura para a próxima evolução do fluxo.")
