from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import blindar_df_para_bling, dataframe_para_csv_bytes


def _voltar() -> None:
    st.session_state["wizard_etapa_atual"] = "mapeamento"
    st.rerun()


def render_preview_final() -> None:
    st.title("3. Exportação")

    df = st.session_state.get("df_mapeado")

    if not isinstance(df, pd.DataFrame) or df.empty:
        st.error("Nenhum dado para preview.")
        return

    tipo_operacao = st.session_state.get("tipo_operacao", "cadastro")
    deposito_nome = st.session_state.get("deposito_nome", "")

    df_export = blindar_df_para_bling(
        df,
        tipo_operacao_bling=tipo_operacao,
        deposito_nome=deposito_nome,
    )
    st.session_state["df_mapeado"] = df_export

    st.success("Arquivo pronto para exportação (modo seguro)")
    st.caption(f"Linhas: {len(df_export)} | Colunas: {len(df_export.columns)}")

    with st.expander("Preview final do arquivo", expanded=False):
        st.dataframe(df_export, use_container_width=True)

    csv = dataframe_para_csv_bytes(df_export)

    st.download_button(
        label="📥 Baixar CSV",
        data=csv,
        file_name="bling_export.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if st.button("⬅️ Voltar", use_container_width=True):
        _voltar()
