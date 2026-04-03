import streamlit as st

from .core.leitor import carregar_planilha, preview, validar_planilha_basica
from .utils.excel import salvar_excel_bytes


def main():
    st.set_page_config(page_title="🔥 Bling Automação PRO", layout="wide")

    st.title("🔥 Bling Automação PRO")
    st.subheader("🧠 Sistema inteligente para planilhas Bling")

    st.header("📂 Upload de planilha")

    arquivo = st.file_uploader(
        "Enviar planilha do fornecedor",
        type=["xlsx", "xls", "csv"],
        key="upload_planilha_principal",
    )

    df = None

    if arquivo is not None:
        try:
            df = carregar_planilha(arquivo)

            if not validar_planilha_basica(df):
                st.error("❌ Planilha vazia ou inválida.")
                st.stop()

            st.success("✅ Planilha carregada com sucesso")

            preview(df)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Linhas", len(df))
            with col2:
                st.metric("Colunas", len(df.columns))

        except Exception as e:
            st.error(f"Erro ao processar a planilha: {e}")
            st.stop()

    st.header("🏬 Estoque de destino")

    deposito = st.text_input(
        "Digite em qual estoque será lançado",
        placeholder="Ex: Geral, Loja, CD"
    )

    if deposito:
        st.success(f"Estoque definido: {deposito}")

    if df is not None:
        st.header("📥 Download")

        try:
            arquivo_excel = salvar_excel_bytes(df)

            st.download_button(
                label="📦 Baixar planilha processada",
                data=arquivo_excel,
                file_name="planilha_processada.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Erro ao gerar arquivo para download: {e}")


if __name__ == "__main__":
    main()
