from typing import Dict, List
import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes


def render_origem_dados():
    st.subheader("📥 Origem dos dados")

    uploaded_file = st.file_uploader("Anexar planilha", type=["xlsx", "xls", "csv"])

    if not uploaded_file:
        return

    df = pd.read_excel(uploaded_file)

    st.success("Arquivo carregado com sucesso!")

    st.write("Preview:")
    st.dataframe(df.head(5), use_container_width=True)

    # =========================
    # PRECIFICAÇÃO
    # =========================
    df = calcular_preco_compra_automatico_df(df)

    # =========================
    # LIMPEZA GTIN
    # =========================

    pendencias_gtin = []
    linhas_invalidas = []

    if "GTIN/EAN" in df.columns:
        df["GTIN/EAN"] = df["GTIN/EAN"].astype(str)

        def validar_gtin(valor, idx):
            if not valor.isdigit():
                pendencias_gtin.append(f"Linha {idx+1}: GTIN inválido ({valor})")
                linhas_invalidas.append(idx)
                return ""

            if len(valor) not in [8, 12, 13, 14]:
                pendencias_gtin.append(f"Linha {idx+1}: GTIN tamanho inválido ({valor})")
                linhas_invalidas.append(idx)
                return ""

            if valor.startswith("687"):
                pendencias_gtin.append(f"Linha {idx+1}: prefixo rejeitado ({valor})")
                linhas_invalidas.append(idx)
                return ""

            return valor

        df["GTIN/EAN"] = [
            validar_gtin(v, i) for i, v in enumerate(df["GTIN/EAN"])
        ]

    # =========================
    # ALERTAS
    # =========================

    if pendencias_gtin:
        st.error(
            f"Foram detectados {len(pendencias_gtin)} GTIN/EAN inválido(s) removidos. Revise o preview."
        )

        with st.expander("Ver ocorrências"):
            for erro in pendencias_gtin:
                st.write(erro)

    # =========================
    # PREVIEW FINAL
    # =========================

    if st.button("Gerar preview final"):
        st.session_state["df_final"] = df

    if "df_final" not in st.session_state:
        return

    df_final = st.session_state["df_final"]

    st.write("Preview final:")
    st.dataframe(df_final.head(10), use_container_width=True)

    # =========================
    # CONTROLE DOWNLOAD
    # =========================

    if pendencias_gtin:
        st.error("Não foi possível liberar o download porque ainda existem pendências.")

        if st.button("⚠️ Forçar limpeza e liberar download"):
            st.session_state["forcar_download"] = True
            st.warning("Download liberado manualmente.")

    liberar_download = not pendencias_gtin or st.session_state.get("forcar_download", False)

    if liberar_download:
        excel_bytes = df_to_excel_bytes(df_final)

        st.success("Download liberado.")

        st.download_button(
            label="📥 Baixar planilha final",
            data=excel_bytes,
            file_name="bling_importacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
