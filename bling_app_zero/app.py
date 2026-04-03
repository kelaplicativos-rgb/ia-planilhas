from pathlib import Path

import pandas as pd
import streamlit as st

from .core.ia_mapper import detectar_colunas_com_ia
from .core.leitor import carregar_planilha, preview, validar_planilha_vazia
from .core.mapeamento_bling import (
    detectar_colunas,
    mapear_cadastro_bling,
    mapear_estoque_bling,
)
from .utils.excel import salvar_excel_bytes


def ler_excel(caminho):
    try:
        df = pd.read_excel(caminho, dtype=object)
        return df, None
    except Exception as e:
        return None, str(e)


def montar_mapeamento_manual(df_origem: pd.DataFrame, colunas_detectadas: dict) -> dict:
    st.subheader("🛠️ Ajuste manual das colunas")
    st.caption("Se alguma coluna estiver errada, ajuste manualmente antes de gerar o arquivo final.")

    opcoes = [""] + list(df_origem.columns)

    campos = [
        "codigo",
        "nome",
        "preco",
        "descricao_curta",
        "marca",
        "imagem",
        "estoque",
        "deposito",
        "situacao",
        "unidade",
    ]

    resultado = {}
    col1, col2 = st.columns(2)

    for i, campo in enumerate(campos):
        detectado = colunas_detectadas.get(campo)
        indice_padrao = opcoes.index(detectado) if detectado in opcoes else 0
        container = col1 if i % 2 == 0 else col2

        with container:
            escolha = st.selectbox(
                label=f"Campo: {campo}",
                options=opcoes,
                index=indice_padrao,
                key=f"map_{campo}",
            )

        resultado[campo] = escolha if escolha else None

    return resultado


def main():
    st.set_page_config(page_title="🔥 Bling Automação PRO", layout="wide")

    st.title("🔥 Bling Automação PRO")
    st.caption("Fluxo inteligente: detecção local primeiro, IA como reforço e correção manual antes de gerar o Bling.")

    base_dir = Path(__file__).parent
    pasta_modelos = base_dir / "modelos"

    arq_prod = pasta_modelos / "produtos.xlsx"
    arq_est = pasta_modelos / "saldo_estoque.xlsx"

    st.header("1️⃣ Origem dos dados")

    origem = st.radio(
        "Selecione a origem:",
        ["📄 Planilha", "🌐 Site (em breve)"],
        horizontal=True,
    )

    df_origem = None
    colunas_finais = None

    if origem == "📄 Planilha":
        st.header("2️⃣ Anexar planilha")

        arquivo = st.file_uploader(
            "Envie qualquer planilha de fornecedor",
            type=["xlsx", "csv"],
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

                colunas_local = detectar_colunas(df_origem)
                faltantes = [chave for chave, valor in colunas_local.items() if not valor]

                usar_ia = st.checkbox(
                    "🧠 Usar IA para melhorar a detecção quando o local não encontrar tudo",
                    value=True,
                )

                colunas_ia = {}
                if usar_ia and faltantes:
                    with st.spinner("🧠 IA analisando colunas faltantes..."):
                        colunas_ia = detectar_colunas_com_ia(df_origem)

                todas_as_chaves = sorted(set(colunas_local.keys()) | set(colunas_ia.keys()))
                colunas_detectadas = {
                    chave: colunas_local.get(chave) or colunas_ia.get(chave)
                    for chave in todas_as_chaves
                }

                st.subheader("🔎 Colunas identificadas automaticamente")
                df_cols = pd.DataFrame(
                    [{"Campo": k, "Coluna detectada": v if v else "Não encontrada"} for k, v in colunas_detectadas.items()]
                )
                st.dataframe(df_cols, width="stretch")

                colunas_finais = montar_mapeamento_manual(df_origem, colunas_detectadas)

                st.subheader("✅ Mapeamento final que será usado")
                df_cols_finais = pd.DataFrame(
                    [{"Campo": k, "Coluna final": v if v else "Não definida"} for k, v in colunas_finais.items()]
                )
                st.dataframe(df_cols_finais, width="stretch")

            except Exception as e:
                st.error(f"❌ Erro ao processar a planilha: {e}")
                st.stop()

    else:
        st.info("🚧 O modo site ficará aqui, separado do fluxo de planilha.")

    if df_origem is not None and colunas_finais is not None:
        st.header("3️⃣ O que deseja fazer?")

        modulo = st.radio(
            "Selecione o módulo:",
            ["📦 Cadastro de Produtos", "📊 Atualização de Estoque"],
            horizontal=True,
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
                        colunas_detectadas=colunas_finais,
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

        else:
            st.subheader("Gerar planilha de estoque")

            deposito = st.text_input(
                "Nome do depósito padrão",
                value="Geral",
                placeholder="Ex.: Geral",
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
                        colunas_detectadas=colunas_finais,
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
