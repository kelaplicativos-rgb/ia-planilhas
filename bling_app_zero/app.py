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


def limpar_total(df):
    df = df.copy()

    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    df = df.replace("None", "")
    df = df.fillna("")
    df = df.iloc[0:0]

    return df


def main():
    st.set_page_config(page_title="🔥 Bling Automação PRO", layout="wide")

    st.title("🔥 Bling Automação PRO")
    st.subheader("🧠 Base limpa para padrão Bling")

    BASE_DIR = Path(__file__).parent
    PASTA_MODELOS = BASE_DIR / "modelos"

    ARQ_PROD = PASTA_MODELOS / "produtos.xlsx"
    ARQ_EST = PASTA_MODELOS / "saldo_estoque.xlsx"

    st.header("📂 Upload de planilha")

    arquivo = st.file_uploader("Enviar planilha", type=["xlsx", "csv"])

    df = None

    if arquivo:
        try:
            df = carregar_planilha(arquivo)

            if validar_planilha_vazia(df):
                st.error("❌ Planilha vazia")
                st.stop()

            st.success("✅ Planilha carregada")

            st.dataframe(preview(df), width="stretch")

        except Exception as e:
            st.error(f"Erro: {e}")

    # 🔥 GERAR BLING
    if df is not None and ARQ_PROD.exists():

        if st.button("🚀 Gerar Bling"):

            try:
                modelo, erro = ler_excel(ARQ_PROD)

                if modelo is None:
                    st.error(erro)
                    st.stop()

                df_bling = mapear_produtos(df, modelo)

                st.success("✅ Gerado")

                st.dataframe(df_bling, width="stretch")

                arquivo_excel = salvar_excel_bytes(df_bling)

                st.download_button(
                    "📥 Baixar",
                    data=arquivo_excel,
                    file_name="bling.xlsx"
                )

            except Exception as e:
                st.error(e)

    st.header("📦 Modelos")

    if ARQ_PROD.exists():
        prod, erro = ler_excel(ARQ_PROD)

        if prod is not None:
            st.success("Produtos OK")
            st.write(list(prod.columns))
            st.dataframe(limpar_total(prod), width="stretch")

    if ARQ_EST.exists():
        est, erro = ler_excel(ARQ_EST)

        if est is not None:
            st.success("Estoque OK")
            st.write(list(est.columns))
            st.dataframe(limpar_total(est), width="stretch")

    st.header("🏬 Depósito")

    deposito = st.text_input("Nome do depósito")

    if deposito:
        st.success(deposito)


if __name__ == "__main__":
    main()
