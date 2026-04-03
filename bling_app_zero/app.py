# bling_app_zero/app.py

import streamlit as st
import pandas as pd
from pathlib import Path

from .core.leitor import carregar_planilha, validar_planilha_vazia
from .utils.excel import gerar_preview, salvar_excel_bytes


def main():
    st.set_page_config(page_title="🔥 Bling Automação PRO", layout="wide")

    st.title("🔥 Bling Automação PRO")
    st.subheader("🧠 Sistema inteligente para planilhas Bling")

    # =========================
    # UPLOAD
    # =========================
    st.header("📂 Upload de planilha")

    arquivo = st.file_uploader(
        "Enviar planilha do fornecedor",
        type=["xlsx", "csv"]
    )

    df = None

    if arquivo:
        try:
            df = carregar_planilha(arquivo)

            if not validar_planilha_vazia(df):
                st.error("❌ Planilha vazia ou inválida")
                st.stop()

            st.success("✅ Planilha carregada com sucesso")

            # =========================
            # PREVIEW (1 LINHA)
            # =========================
            with st.expander("👀 Preview", expanded=False):
                st.dataframe(gerar_preview(df, 1), use_container_width=True)

            # =========================
            # INFO
            # =========================
            col1, col2 = st.columns(2)

            with col1:
                st.metric("Linhas", len(df))

            with col2:
                st.metric("Colunas", len(df.columns))

        except Exception as e:
            st.error(f"Erro ao processar: {e}")
            st.stop()

    # =========================
    # ESTOQUE (campo manual)
    # =========================
    st.header("🏬 Definir estoque de destino")

    deposito = st.text_input("Digite o nome do estoque (ex: Geral, Loja, CD)")

    if deposito:
        st.success(f"Estoque definido: {deposito}")

    # =========================
    # DOWNLOAD TESTE
    # =========================
    if df is not None:
        if st.button("📥 Gerar planilha de teste"):

            try:
                arquivo_excel = salvar_excel_bytes(df)

                st.download_button(
                    label="📦 Baixar planilha",
                    data=arquivo_excel,
                    file_name="planilha_processada.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            except Exception as e:
                st.error(f"Erro ao gerar arquivo: {e}")


if __name__ == "__main__":
    main()
