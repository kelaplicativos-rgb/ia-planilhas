from __future__ import annotations

import streamlit as st


def _voltar() -> None:
    st.session_state["wizard_etapa_atual"] = "mapeamento"
    st.rerun()


def render_preview_final() -> None:
    st.title("3. Exportação")

    df = st.session_state.get("df_mapeado")

    if df is None:
        st.error("Nenhum dado para preview.")
        return

    st.success("Arquivo pronto para exportação (modo seguro)")
    st.caption(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")

    with st.expander("Preview final do arquivo", expanded=False):
        st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')

    st.download_button(
        label="📥 Baixar CSV",
        data=csv,
        file_name="bling_export.csv",
        mime="text/csv",
        use_container_width=True
    )

    if st.button("⬅️ Voltar", use_container_width=True):
        _voltar()
