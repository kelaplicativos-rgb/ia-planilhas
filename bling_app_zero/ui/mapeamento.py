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

# 🔥 NOVO MOTOR DE ESTOQUE
from bling_app_zero.core.stock_intelligence import (
    build_stock_dataframe,
    build_stock_mapping,
    validate_stock_dataframe,
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

    # 🔥 MODO ESTOQUE INTELIGENTE
    if tipo_operacao == "estoque":
        st.subheader("🧠 Estoque inteligente")

        mapping = build_stock_mapping(df, deposito)
        df_final = build_stock_dataframe(df, mapping, deposito)

        erros = validate_stock_dataframe(df_final)

        if erros:
            st.error("⚠️ Problemas detectados no estoque:")
            for erro in erros:
                st.write(f"- {erro}")
        else:
            st.success("✔️ Estoque validado com sucesso.")

        st.session_state["df_mapeado"] = df_final

        st.subheader("Preview estoque")
        st.dataframe(df_final.head(20), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Voltar", use_container_width=True):
                _voltar()
        with col2:
            if st.button("Avançar ➡️", use_container_width=True):
                _avancar()

        return

    # 🔵 FLUXO NORMAL (CADASTRO)

    fornecedor_id = supplier_signature(df)

    memoria = load_memory()
    aprendido = get_supplier_memory(memoria, fornecedor_id)

    st.caption(f"Fornecedor ID: {fornecedor_id}")

    col_limpeza, col_info = st.columns([1, 2])
    with col_limpeza:
        if st.button("🧹 Limpeza automática", use_container_width=True):
            df = aplicar_limpeza(df)
            st.session_state["df_origem"] = df
            st.success("Dados limpos automaticamente.")
    with col_info:
        if aprendido:
            st.success("🧠 Padrão aprendido encontrado para esta estrutura de fornecedor.")
        else:
            st.info("Primeira leitura desta estrutura. Ajuste e salve para ensinar o sistema.")

    sugestoes = suggest_mapping(df, tipo_operacao, learned_mapping=aprendido)

    mapping: dict[str, str] = {}

    st.subheader("Auto mapeamento")

    if not sugestoes:
        st.warning("Nenhuma sugestão forte encontrada.")

    for sugestao in sugestoes:
        emoji = "🧠" if sugestao.confidence == 99 else ("🟢" if sugestao.confidence >= 85 else "🟡")
        st.write(f"{emoji} {sugestao.target} → {sugestao.source} ({sugestao.confidence}%)")
        mapping[sugestao.target] = sugestao.source

    st.subheader("Ajuste manual")

    for target in mapping:
        opcoes = [""] + list(df.columns)
        atual = mapping.get(target, "")
        escolha = st.selectbox(
            target,
            opcoes,
            index=opcoes.index(atual) if atual in opcoes else 0,
            key=_mapping_key(target),
        )
        if escolha:
            mapping[target] = escolha

    df_final = build_mapped_dataframe(df, mapping, tipo_operacao, deposito)

    erros = validar_df_bling(df_final)
    if erros:
        st.error("⚠️ Problemas detectados:")
        for erro in erros:
            st.write(f"- {erro}")
    else:
        st.success("✔️ Pronto para o Bling.")

    st.session_state["df_mapeado"] = df_final

    st.subheader("Preview final")
    st.dataframe(df_final.head(20), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            _voltar()
    with col2:
        if st.button("Avançar ➡️", use_container_width=True):
            _avancar()
