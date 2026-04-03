import streamlit as st
import pandas as pd
from pathlib import Path

from bling_app_zero.core.leitor import carregar_planilha, preview, validar_planilha_vazia
from bling_app_zero.core.mapeamento_bling import (
    detectar_colunas,
    mapear_cadastro_bling,
    mapear_estoque_bling,
)
from bling_app_zero.core.ia_mapper import detectar_colunas_com_ia
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
    st.caption("Transforme qualquer planilha em padrão Bling com IA.")

    base_dir = Path(__file__).parent
    pasta_modelos = base_dir / "modelos"

    arq_prod = pasta_modelos / "produtos.xlsx"
    arq_est = pasta_modelos / "saldo_estoque.xlsx"

    # =========================
    # ORIGEM
    # =========================
    st.header("1️⃣ Origem dos dados")

    origem = st.radio(
        "Selecione:",
        ["📄 Planilha", "🌐 Site (em breve)"],
        horizontal=True
    )

    df_origem = None
    colunas_detectadas = None

    # =========================
    # UPLOAD
    # =========================
    if origem == "📄 Planilha":

        st.header("2️⃣ Anexar planilha")

        arquivo = st.file_uploader("Envie qualquer planilha", type=["xlsx", "csv"])

        if arquivo:
            df_origem = carregar_planilha(arquivo)

            if validar_planilha_vazia(df_origem):
                st.error("❌ Planilha inválida")
                st.stop()

            st.success("✅ Planilha carregada")

            st.dataframe(preview(df_origem, 10), width="stretch")

            # =========================
            # IA + FALLBACK
            # =========================
            with st.spinner("🧠 IA analisando colunas..."):
                colunas_ia = detectar_colunas_com_ia(df_origem)

            colunas_local = detectar_colunas(df_origem)

            # mistura IA + fallback
            colunas_detectadas = {
                k: colunas_ia.get(k) or colunas_local.get(k)
                for k in set(colunas_ia) | set(colunas_local)
            }

            # =========================
            # MOSTRAR RESULTADO
            # =========================
            st.subheader("🔎 Colunas identificadas")

            df_cols = pd.DataFrame([
                {"Campo": k, "Coluna": v if v else "Não encontrada"}
                for k, v in colunas_detectadas.items()
            ])

            st.dataframe(df_cols, width="stretch")

    else:
        st.info("🚧 Módulo site será ativado em breve")

    # =========================
    # MÓDULO
    # =========================
    if df_origem is not None:

        st.header("3️⃣ O que deseja fazer?")

        modulo = st.radio(
            "",
            ["📦 Cadastro", "📊 Estoque"],
            horizontal=True
        )

        # =========================
        # CADASTRO
        # =========================
        if modulo == "📦 Cadastro":

            if st.button("🚀 Gerar cadastro Bling", width="stretch"):

                modelo, erro = ler_excel(arq_prod)

                df_saida = mapear_cadastro_bling(
                    df_origem,
                    modelo,
                    colunas_detectadas
                )

                st.dataframe(df_saida, width="stretch")

                st.download_button(
                    "📥 Baixar",
                    salvar_excel_bytes(df_saida),
                    "bling_cadastro.xlsx"
                )

        # =========================
        # ESTOQUE
        # =========================
        if modulo == "📊 Estoque":

            deposito = st.text_input("Depósito padrão")

            if st.button("🚀 Gerar estoque Bling", width="stretch"):

                modelo, erro = ler_excel(arq_est)

                df_saida = mapear_estoque_bling(
                    df_origem,
                    modelo,
                    colunas_detectadas,
                    deposito
                )

                st.dataframe(df_saida, width="stretch")

                st.download_button(
                    "📥 Baixar",
                    salvar_excel_bytes(df_saida),
                    "bling_estoque.xlsx"
                )


if __name__ == "__main__":
    main()
