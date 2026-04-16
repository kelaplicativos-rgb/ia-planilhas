
from __future__ import annotations

import pandas as pd
import streamlit as st


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.fillna("").to_csv(index=False, sep=";").encode("utf-8-sig")


def render_preview_final() -> None:
    st.markdown("### Preview final")
    st.caption("Confira se as colunas foram mapeadas corretamente antes de baixar.")

    df_final = st.session_state.get("df_final")
    if df_final is None or df_final.empty:
        st.warning("O preview ainda não está pronto. Conclua o mapeamento primeiro.")
        return

    with st.container(border=True):
        st.markdown("#### Conferência final")
        st.dataframe(df_final.head(100), use_container_width=True)

    with st.expander("Ver tabela completa", expanded=False):
        st.dataframe(df_final, use_container_width=True)

    st.success("Confirme acima se as colunas e os valores estão corretos.")

    tipo = st.session_state.get("tipo_operacao", "cadastro")
    nome = "bling_cadastro_final.csv" if tipo == "cadastro" else "bling_estoque_final.csv"

    st.download_button(
        "Baixar planilha final",
        data=_csv_bytes(df_final),
        file_name=nome,
        mime="text/csv",
        use_container_width=True,
    )
