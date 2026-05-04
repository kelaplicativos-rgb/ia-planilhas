from __future__ import annotations

import streamlit as st


def _voltar() -> None:
    st.session_state["wizard_etapa_atual"] = "mapeamento"
    st.rerun()


def render_preview_final() -> None:
    st.title("4. Preview Final")

    df = st.session_state.get("df_mapeado")

    if df is None:
        st.error("Nenhum dado para preview.")
        return

    st.dataframe(df, use_container_width=True)

    st.success("Arquivo pronto para exportação (modo seguro)")

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
