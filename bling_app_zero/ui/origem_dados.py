import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_ia import mapear_colunas_ia
from bling_app_zero.core.memoria_fornecedor import (
    salvar_mapeamento,
    recuperar_mapeamento,
)
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df
from bling_app_zero.utils.excel import df_to_excel_bytes


COLUNAS_DESTINO = [
    "nome",
    "preco",
    "custo",
    "sku",
    "gtin",
    "ncm",
    "marca",
    "estoque",
    "categoria",
    "peso",
]


def render_origem_dados() -> None:
    st.title("IA Automática com Memória")

    arquivo = st.file_uploader(
        "Anexar planilha ou XML",
        type=["xlsx", "xls", "csv", "xml"],
    )

    if not arquivo:
        return

    try:
        nome_arquivo = str(arquivo.name).lower()

        if nome_arquivo.endswith(".xml"):
            df = pd.read_xml(arquivo)
        elif nome_arquivo.endswith(".csv"):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return

    if df is None or df.empty:
        st.warning("O arquivo foi lido, mas não possui dados para processar.")
        return

    colunas_origem = list(df.columns)

    memoria = st.session_state.get("mapeamento_memoria", {})
    mapeamento_memoria = recuperar_mapeamento(memoria, colunas_origem)

    if mapeamento_memoria:
        st.success("⚡ Mapeamento recuperado automaticamente (memória)")
        mapeamento_final = dict(mapeamento_memoria)
    else:
        mapa_ia = mapear_colunas_ia(colunas_origem, COLUNAS_DESTINO)
        mapeamento_final = {}

        for col, dados in mapa_ia.items():
            destino = dados.get("destino")
            score = dados.get("score", 0)

            if destino and score >= 0.6:
                mapeamento_final[col] = destino

    st.subheader("Preview do mapeamento")

    df_preview = pd.DataFrame()
    for origem, destino in mapeamento_final.items():
        if origem in df.columns:
            df_preview[destino] = df[origem]

    if not df_preview.empty:
        st.dataframe(df_preview.head(3), use_container_width=True)
    else:
        st.info("Nenhum campo foi mapeado automaticamente até o momento.")

    if st.button("Gerar automático", use_container_width=True):
        try:
            df_saida = pd.DataFrame()

            for origem, destino in mapeamento_final.items():
                if origem in df.columns:
                    df_saida[destino] = df[origem]

            if df_saida.empty:
                st.warning("Nenhum dado pôde ser gerado porque não houve mapeamento válido.")
                return

            df_saida = calcular_preco_compra_automatico_df(df_saida)

            salvar_mapeamento(memoria, colunas_origem, mapeamento_final)
            st.session_state["mapeamento_memoria"] = memoria

            excel_bytes = df_to_excel_bytes(df_saida)

            st.download_button(
                "Baixar",
                data=excel_bytes,
                file_name="bling_auto.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            st.success("Aprendido e gerado automaticamente.")
        except Exception as e:
            st.error(f"Erro ao gerar arquivo: {e}")


def tela_origem_dados() -> None:
    render_origem_dados()
