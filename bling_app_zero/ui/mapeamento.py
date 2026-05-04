from __future__ import annotations

import streamlit as st

from bling_app_zero.core.auto_mapper import suggest_mapping, build_mapped_dataframe, supplier_signature


def _avancar():
    st.session_state["wizard_etapa_atual"] = "preview_final"
    st.rerun()


def _voltar():
    st.session_state["wizard_etapa_atual"] = "precificacao"
    st.rerun()


def render_origem_mapeamento():
    st.title("3. BLINGAUTO GOD MODE")

    df = st.session_state.get("df_origem")
    if df is None or df.empty:
        st.error("Nenhuma planilha carregada")
        return

    tipo = st.session_state.get("tipo_operacao", "cadastro")

    sig = supplier_signature(df)
    memoria = st.session_state.setdefault("auto_map_memory", {})
    aprendido = memoria.get(sig, {})

    st.caption(f"Assinatura fornecedor: {sig}")

    sugestoes = suggest_mapping(df, tipo, learned_mapping=aprendido)

    mapping = {}

    st.subheader("Sugestão automática")

    for s in sugestoes:
        emoji = "🧠" if s.confidence == 99 else ("🟢" if s.confidence > 85 else "🟡")
        st.write(f"{emoji} {s.target} → {s.source} ({s.confidence}%)")
        mapping[s.target] = s.source

    st.subheader("Correção manual (ensina o sistema)")

    for target in mapping:
        escolha = st.selectbox(
            target,
            options=[""] + list(df.columns),
            index=list(df.columns).index(mapping[target]) if mapping[target] in df.columns else 0,
            key=f"map_{target}",
        )
        if escolha:
            mapping[target] = escolha

    if st.button("💾 Aprender este padrão", use_container_width=True):
        memoria[sig] = mapping.copy()
        st.success("Padrão salvo! Próximas planilhas iguais serão automáticas.")

    deposito = st.session_state.get("deposito_nome")

    df_final = build_mapped_dataframe(df, mapping, tipo, deposito)

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
