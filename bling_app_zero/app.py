import streamlit as st
import pandas as pd
from pathlib import Path

from bling_app_zero.core.leitor import carregar_planilha, preview, validar_planilha_vazia
from bling_app_zero.core.mapeamento_bling import mapear_produtos
from bling_app_zero.utils.excel import salvar_excel_bytes


def ler_excel(caminho):
    try:
        df = pd.read_excel(caminho)
        return df, None
    except Exception as e:
        return None, str(e)


def main():
    st.set_page_config(page_title="🔥 Bling Automação PRO", layout="wide")

    st.title("🔥 Bling Automação PRO")

    # =========================
    # 🔹 ESCOLHA DA ORIGEM
    # =========================
    st.header("📡 Origem dos dados")

    origem = st.radio(
        "Selecione a origem:",
        ["📄 Planilha", "🌐 Site (em breve)"],
        horizontal=True
    )

    # =========================
    # 🔹 ESCOLHA DO MÓDULO
    # =========================
    st.header("⚙️ Módulo")

    modulo = st.radio(
        "O que deseja fazer?",
        ["📦 Cadastro de Produtos", "📊 Atualização de Estoque"],
        horizontal=True
    )

    BASE_DIR = Path(__file__).parent
    PASTA_MODELOS = BASE_DIR / "modelos"

    ARQ_PROD = PASTA_MODELOS / "produtos.xlsx"
    ARQ_EST = PASTA_MODELOS / "saldo_estoque.xlsx"

    df = None

    # =========================
    # 📄 PLANILHA
    # =========================
    if origem == "📄 Planilha":

        st.header("📂 Upload")

        arquivo = st.file_uploader(
            "Envie sua planilha",
            type=["xlsx", "csv"]
        )

        if arquivo:
            try:
                df = carregar_planilha(arquivo)

                if validar_planilha_vazia(df):
                    st.error("❌ Planilha vazia")
                    st.stop()

                st.success("✅ Planilha carregada")

                st.subheader("👀 Preview")
                st.dataframe(preview(df), width="stretch")

            except Exception as e:
                st.error(f"Erro: {e}")

    # =========================
    # 🌐 SITE (FUTURO)
    # =========================
    else:
        st.info("🔧 Módulo de extração por site será ativado em breve")

    # =========================
    # 📦 CADASTRO PRODUTOS
    # =========================
    if modulo == "📦 Cadastro de Produtos":

        if df is not None and ARQ_PROD.exists():

            if st.button("🚀 Gerar Cadastro Bling"):

                try:
                    modelo, erro = ler_excel(ARQ_PROD)

                    if modelo is None:
                        st.error(erro)
                        st.stop()

                    df_bling = mapear_produtos(df, modelo)

                    st.success("✅ Cadastro gerado")

                    st.dataframe(df_bling, width="stretch")

                    arquivo_excel = salvar_excel_bytes(df_bling)

                    st.download_button(
                        "📥 Baixar cadastro",
                        data=arquivo_excel,
                        file_name="bling_cadastro.xlsx"
                    )

                except Exception as e:
                    st.error(e)

    # =========================
    # 📊 ESTOQUE
    # =========================
    elif modulo == "📊 Atualização de Estoque":

        deposito = st.text_input("🏬 Nome do depósito")

        if df is not None and ARQ_EST.exists():

            if st.button("🚀 Gerar Estoque Bling"):

                try:
                    modelo, erro = ler_excel(ARQ_EST)

                    if modelo is None:
                        st.error(erro)
                        st.stop()

                    df_estoque = modelo.copy()

                    # 🔥 EXEMPLO SIMPLES (iremos evoluir)
                    if "codigo" in df.columns:
                        df_estoque["codigo"] = df["codigo"]

                    if deposito:
                        df_estoque["deposito"] = deposito

                    st.success("✅ Estoque gerado")

                    st.dataframe(df_estoque, width="stretch")

                    arquivo_excel = salvar_excel_bytes(df_estoque)

                    st.download_button(
                        "📥 Baixar estoque",
                        data=arquivo_excel,
                        file_name="bling_estoque.xlsx"
                    )

                except Exception as e:
                    st.error(e)


if __name__ == "__main__":
    main()
