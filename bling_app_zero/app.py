import streamlit as st
import pandas as pd
from pathlib import Path

from bling_app_zero.core.leitor import carregar_planilha, preview, validar_planilha_vazia


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

    # =========================
    # CAMINHOS
    # =========================
    BASE_DIR = Path(__file__).parent
    PASTA_MODELOS = BASE_DIR / "modelos"

    ARQ_PROD = PASTA_MODELOS / "produtos.xlsx"
    ARQ_EST = PASTA_MODELOS / "saldo_estoque.xlsx"

    # =========================
    # UPLOAD INTELIGENTE
    # =========================
    st.header("📂 Upload de planilha (modo inteligente)")

    arquivo = st.file_uploader(
        "Enviar planilha para processamento",
        type=["xlsx", "csv"]
    )

    if arquivo:
        try:
            df = carregar_planilha(arquivo)

            if validar_planilha_vazia(df):
                st.error("❌ Planilha vazia ou inválida")
                st.stop()

            st.success("✅ Planilha carregada com sucesso")

            st.subheader("👀 Preview")
            st.dataframe(preview(df), use_container_width=True)

            st.subheader("📊 Informações")
            col1, col2 = st.columns(2)

            with col1:
                st.metric("Linhas", len(df))

            with col2:
                st.metric("Colunas", len(df.columns))

        except Exception as e:
            st.error(f"Erro ao processar: {e}")

    # =========================
    # MODELOS BLING
    # =========================
    st.header("📦 Verificação dos modelos")

    # =========================
    # PRODUTOS
    # =========================
    if ARQ_PROD.exists():
        prod, erro = ler_excel(ARQ_PROD)

        if prod is not None:
            st.success("✅ produtos.xlsx carregado")

            st.write("📊 Colunas detectadas:")
            st.write(list(prod.columns))

            prod_limpo = limpar_total(prod)

            st.write("🧼 Estrutura após limpeza:")
            st.dataframe(prod_limpo, use_container_width=True)

            st.info(f"Colunas: {len(prod_limpo.columns)} | Linhas: {len(prod_limpo)}")

        else:
            st.error(f"Erro: {erro}")
    else:
        st.error("❌ produtos.xlsx não encontrado")

    # =========================
    # ESTOQUE
    # =========================
    if ARQ_EST.exists():
        est, erro = ler_excel(ARQ_EST)

        if est is not None:
            st.success("✅ saldo_estoque.xlsx carregado")

            st.write("📊 Colunas detectadas:")
            st.write(list(est.columns))

            est_limpo = limpar_total(est)

            st.write("🧼 Estrutura após limpeza:")
            st.dataframe(est_limpo, use_container_width=True)

            st.info(f"Colunas: {len(est_limpo.columns)} | Linhas: {len(est_limpo)}")

        else:
            st.error(f"Erro: {erro}")
    else:
        st.error("❌ saldo_estoque.xlsx não encontrado")

    # =========================
    # DEPÓSITO
    # =========================
    st.header("🏬 Depósito manual")

    deposito = st.text_input("Digite o nome do depósito (ex: Geral, Loja, CD)")

    if deposito:
        st.success(f"Depósito definido: {deposito}")


if __name__ == "__main__":
    main()
