from __future__ import annotations

import streamlit as st

from bling_app_zero.core.auto_mapper import (
    build_mapped_dataframe,
    suggest_mapping,
    supplier_signature,
)
from bling_app_zero.core.auto_map_memory import (
    delete_supplier_memory,
    get_supplier_memory,
    load_memory,
    save_memory,
    set_supplier_memory,
)
from bling_app_zero.core.bling_validator import validar_df_bling
from bling_app_zero.core.data_cleaner import aplicar_limpeza

from bling_app_zero.core.stock_intelligence import (
    build_stock_dataframe,
    build_stock_mapping,
    validate_stock_dataframe,
)

# 🔥 NOVO PRO
from bling_app_zero.core.stock_pro import (
    apply_stock_mode,
    add_stock_delta,
    stock_risk_summary,
    block_stock_export,
)


def _avancar() -> None:
    st.session_state["wizard_etapa_atual"] = "preview_final"
    st.session_state["wizard_etapa_maxima"] = "preview_final"
    st.rerun()


def _voltar() -> None:
    st.session_state["wizard_etapa_atual"] = "precificacao"
    st.rerun()


def _mapping_key(target: str) -> str:
    return f"blingauto_map_{target}"


def render_origem_mapeamento() -> None:
    st.title("3. BLINGAUTO SUPREMO")

    df = st.session_state.get("df_origem")
    if df is None or df.empty:
        st.error("Nenhuma planilha carregada.")
        return

    tipo_operacao = st.session_state.get("tipo_operacao", "cadastro")
    deposito = st.session_state.get("deposito_nome")

    # 🚀 ESTOQUE PRO
    if tipo_operacao == "estoque":
        st.subheader("🧠 Estoque PRO")

        modo = st.radio("Modo", ["substituir", "entrada", "saida"], horizontal=True)

        mapping = build_stock_mapping(df, deposito)
        df_final = build_stock_dataframe(df, mapping, deposito)
        df_final = apply_stock_mode(df_final, modo)
        df_final = add_stock_delta(df_final)

        resumo = stock_risk_summary(df_final)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Linhas", resumo["linhas"])
        c2.metric("Negativos", resumo["negativos"])
        c3.metric("Vazios", resumo["vazios"])
        c4.metric("Risco", resumo["variacao_alta"])

        erros = validate_stock_dataframe(df_final)
        bloqueios = block_stock_export(df_final)

        if erros:
            st.warning("⚠️ Problemas:")
            for e in erros:
                st.write("-", e)

        if bloqueios:
            st.error("🚫 BLOQUEADO:")
            for b in bloqueios:
                st.write("-", b)

        st.session_state["df_mapeado"] = df_final

        st.dataframe(df_final.head(20), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Voltar"):
                _voltar()
        with col2:
            if st.button("Avançar ➡️", disabled=bool(bloqueios)):
                _avancar()

        return

    # 🔵 fluxo normal
    fornecedor_id = supplier_signature(df)
    memoria = load_memory()
    aprendido = get_supplier_memory(memoria, fornecedor_id)

    sugestoes = suggest_mapping(df, tipo_operacao, learned_mapping=aprendido)
    mapping: dict[str, str] = {}

    for s in sugestoes:
        mapping[s.target] = s.source

    df_final = build_mapped_dataframe(df, mapping, tipo_operacao, deposito)

    erros = validar_df_bling(df_final)
    if erros:
        st.error("⚠️ Problemas:")
        for e in erros:
            st.write("-", e)
    else:
        st.success("✔️ OK")

    st.session_state["df_mapeado"] = df_final

    st.dataframe(df_final.head(20), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar"):
            _voltar()
    with col2:
        if st.button("Avançar ➡️"):
            _avancar()
