import streamlit as st
import pandas as pd
from pathlib import Path

from bling_app_zero.core.leitor import carregar_planilha, preview, validar_planilha_vazia
from bling_app_zero.core.mapeamento_bling import (
    detectar_colunas,
    mapear_cadastro_bling,
    mapear_estoque_bling,
)
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
    st.caption("Painel modular para transformar planilhas de fornecedores em arquivos prontos para o Bling.")

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
        st.write("Envie qualquer planilha de fornecedor. O sistema tentará identificar automaticamente os dados.")

        arquivo = st.file_uploader(
            "Anexar planilha de produtos",
            type=["xlsx", "csv"]
        )

        if arquivo:
            try:
                df_origem = carregar_planilha(arquivo)

                if validar_planilha_vazia(df_origem):
                    st.error("❌ A planilha enviada está vazia ou inválida.")
                    st.stop()

                colunas_detectadas = detectar_colunas(df_origem)

                st.success("✅ Planilha carregada e analisada com sucesso.")

                st.subheader("Preview da planilha enviada")
                st.dataframe(preview(df_origem, linhas=10), width="stretch")

                st.subheader("Colunas identificadas automaticamente")
                resumo_detectado = pd.DataFrame(
                    [
                        {"Campo lógico": campo, "Coluna encontrada": coluna if coluna else "Não identificada"}
                        for campo, coluna in colunas_detectadas.items()
                    ]
                )
                st.dataframe(resumo_detectado, width="stretch")

            except Exception as e:
                st.error(f"❌ Erro ao processar a planilha: {e}")
                st.stop()

    else:
        st.header("2️⃣ Extração por site")
        st.info("🔧 O modo de extração por site ficará nesta etapa do fluxo, sem misturar com o restante do painel.")

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
                st.error("❌ O modelo produtos.xlsx não foi encontrado na pasta modelos.")
                st.stop()

            if st.button("🚀 Gerar cadastro Bling", width="stretch"):
                try:
                    modelo_prod, erro = ler_excel(arq_prod)

                    if modelo_prod is None:
                        st.error(f"❌ Erro ao abrir modelo de cadastro: {erro}")
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
                        width="stretch",
                    )

                except Exception as e:
                    st.error(f"❌ Erro ao gerar cadastro: {e}")

        elif modulo == "📊 Atualização de Estoque":
            st.subheader("Gerar planilha de estoque")

            deposito = st.text_input("Nome do depósito padrão", placeholder="Ex.: Geral")

            if not arq_est.exists():
                st.error("❌ O modelo saldo_estoque.xlsx não foi encontrado na pasta modelos.")
                st.stop()

            if st.button("🚀 Gerar estoque Bling", width="stretch"):
                try:
                    modelo_est, erro = ler_excel(arq_est)

                    if modelo_est is None:
                        st.error(f"❌ Erro ao abrir modelo de estoque: {erro}")
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
                        width="stretch",
                    )

                except Exception as e:
                    st.error(f"❌ Erro ao gerar estoque: {e}")


if __name__ == "__main__":
    main()
