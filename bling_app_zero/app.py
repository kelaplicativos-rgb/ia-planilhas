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
    st.caption("Transforme qualquer planilha em padrão Bling com IA e fallback local.")

    base_dir = Path(__file__).parent
    pasta_modelos = base_dir / "modelos"

    arq_prod = pasta_modelos / "produtos.xlsx"
    arq_est = pasta_modelos / "saldo_estoque.xlsx"

    st.header("1️⃣ Origem dos dados")

    origem = st.radio(
        "Selecione a origem:",
        ["📄 Planilha", "🌐 Site (em breve)"],
        horizontal=True
    )

    df_origem = None
    colunas_detectadas = None

    if origem == "📄 Planilha":
        st.header("2️⃣ Anexar planilha")

        arquivo = st.file_uploader(
            "Envie qualquer planilha de fornecedor",
            type=["xlsx", "csv"]
        )

        if arquivo:
            try:
                df_origem = carregar_planilha(arquivo)

                if validar_planilha_vazia(df_origem):
                    st.error("❌ A planilha enviada está vazia ou inválida.")
                    st.stop()

                st.success("✅ Planilha carregada com sucesso.")

                st.subheader("👀 Preview")
                st.dataframe(preview(df_origem, linhas=10), width="stretch")

                with st.spinner("🧠 IA analisando colunas..."):
                    colunas_ia = detectar_colunas_com_ia(df_origem)

                colunas_local = detectar_colunas(df_origem)

                # IA primeiro, fallback local depois
                todas_as_chaves = sorted(set(colunas_ia.keys()) | set(colunas_local.keys()))
                colunas_detectadas = {
                    chave: colunas_ia.get(chave) or colunas_local.get(chave)
                    for chave in todas_as_chaves
                }

                st.subheader("🔎 Colunas identificadas")
                df_cols = pd.DataFrame([
                    {"Campo": k, "Coluna": v if v else "Não encontrada"}
                    for k, v in colunas_detectadas.items()
                ])
                st.dataframe(df_cols, width="stretch")

            except Exception as e:
                st.error(f"❌ Erro ao processar a planilha: {e}")
                st.stop()

    else:
        st.info("🚧 O modo site será ativado nesta etapa futuramente.")

    if df_origem is not None:
        st.header("3️⃣ O que deseja fazer?")

        modulo = st.radio(
            "Selecione o módulo:",
            ["📦 Cadastro de Produtos", "📊 Atualização de Estoque"],
            horizontal=True
        )

        if modulo == "📦 Cadastro de Produtos":
            st.subheader("Gerar planilha de cadastro")

            if not arq_prod.exists():
                st.error("❌ O modelo produtos.xlsx não foi encontrado.")
                st.stop()

            if st.button("🚀 Gerar cadastro Bling", width="stretch"):
                try:
                    modelo_prod, erro = ler_excel(arq_prod)

                    if modelo_prod is None:
                        st.error(f"❌ Erro ao abrir o modelo de cadastro: {erro}")
                        st.stop()

                    df_saida = mapear_cadastro_bling(
                        df_origem=df_origem,
                        modelo=modelo_prod,
                        colunas_detectadas=colunas_detectadas,
                    )

                    st.success("✅ Planilha de cadastro gerada com sucesso.")
                    st.dataframe(df_saida, width="stretch")

                    arquivo_excel = salvar_excel_bytes(df_saida, nome_aba="Cadastro")
                    st.download_button(
                        label="📥 Baixar planilha de cadastro",
                        data=arquivo_excel,
                        file_name="bling_cadastro_produtos.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch"
                    )

                except Exception as e:
                    st.error(f"❌ Erro ao gerar cadastro: {e}")

        elif modulo == "📊 Atualização de Estoque":
            st.subheader("Gerar planilha de estoque")

            deposito = st.text_input(
                "Nome do depósito padrão",
                value="Geral",
                placeholder="Ex.: Geral"
            )

            if not arq_est.exists():
                st.error("❌ O modelo saldo_estoque.xlsx não foi encontrado.")
                st.stop()

            if st.button("🚀 Gerar estoque Bling", width="stretch"):
                try:
                    modelo_est, erro = ler_excel(arq_est)

                    if modelo_est is None:
                        st.error(f"❌ Erro ao abrir o modelo de estoque: {erro}")
                        st.stop()

                    df_saida = mapear_estoque_bling(
                        df_origem=df_origem,
                        modelo=modelo_est,
                        colunas_detectadas=colunas_detectadas,
                        deposito_padrao=deposito.strip(),
                    )

                    st.success("✅ Planilha de estoque gerada com sucesso.")
                    st.dataframe(df_saida, width="stretch")

                    arquivo_excel = salvar_excel_bytes(df_saida, nome_aba="Estoque")
                    st.download_button(
                        label="📥 Baixar planilha de estoque",
                        data=arquivo_excel,
                        file_name="bling_atualizacao_estoque.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width="stretch"
                    )

                except Exception as e:
                    st.error(f"❌ Erro ao gerar estoque: {e}")


if __name__ == "__main__":
    main()
