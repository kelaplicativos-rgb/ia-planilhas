from __future__ import annotations

import streamlit as st
import pandas as pd

from bling_app_zero.core.auto_mapper import suggest_mapping, build_mapped_dataframe


def _avancar() -> None:
    st.session_state["wizard_etapa_atual"] = "preview_final"
    st.session_state["wizard_etapa_maxima"] = "preview_final"
    st.rerun()


def _voltar() -> None:
    st.session_state["wizard_etapa_atual"] = "precificacao"
    st.rerun()


def render_origem_mapeamento() -> None:
    st.title("3. Mapeamento Inteligente")

    df = st.session_state.get("df_origem")

    if df is None or df.empty:
        st.error("Nenhuma planilha carregada.")
        return

    st.subheader("Pré-visualização da base")
    st.dataframe(df.head(20), use_container_width=True)

    tipo_operacao = st.session_state.get("tipo_operacao", "cadastro")

    st.subheader("Sugestão automática (BLINGAUTO)")

    suggestions = suggest_mapping(df, tipo_operacao)

    if not suggestions:
        st.warning("Nenhum mapeamento automático forte encontrado.")

    mapping: dict[str, str] = {}

    for s in suggestions:
        emoji = "🟢" if s.confidence >= 85 else "🟡"
        st.write(f"{emoji} {s.target} → {s.source} ({s.confidence}%)")
        mapping[s.target] = s.source

    st.divider()

    st.subheader("Ajuste manual (opcional)")

    for target in sorted(set(mapping.keys())):
        options = [""] + list(df.columns)
        current = mapping.get(target, "")
        choice = st.selectbox(
            f"{target}",
            options,
            index=options.index(current) if current in options else 0,
            key=f"map_{target}",
        )
        if choice:
            mapping[target] = choice

    df_final = build_mapped_dataframe(df, mapping, tipo_operacao)

    st.session_state["df_mapeado"] = df_final

    st.subheader("Preview mapeado")
    st.dataframe(df_final.head(20), use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            _voltar()

    with col2:
        if st.button("Avançar para preview ➡️", use_container_width=True):
            _avancar()
