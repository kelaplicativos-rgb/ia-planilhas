import streamlit as st

from .core.leitor import carregar_planilha, preview, validar_planilha_basica
from .utils.excel import salvar_excel_bytes


def main():
    st.set_page_config(page_title="Bling PRO", layout="wide")

    st.title("🔥 Bling Automação")

    arquivo = st.file_uploader("Enviar planilha")

    df = None

    if arquivo:
        df = carregar_planilha(arquivo)

        if not validar_planilha_basica(df):
            st.error("Planilha inválida")
            return

        st.success("Planilha carregada")

        preview(df)

    st.header("📦 Estoque")

    estoque = st.text_input("Digite o estoque")

    if df is not None:
        if st.button("Gerar planilha"):
            excel = salvar_excel_bytes(df)

            st.download_button(
                "Baixar",
                excel,
                "saida.xlsx"
            )


if __name__ == "__main__":
    main()
