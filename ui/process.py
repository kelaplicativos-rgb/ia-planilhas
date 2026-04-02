import io
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

from core.logger import logs
from core.reader import ler_planilha
from core.scraper import coletar_links_site, extrair_site
from core.normalizer import normalizar_planilha_entrada
from core.bling.estoque import preencher_modelo_estoque
from core.bling.cadastro import preencher_modelo_cadastro
from core.merger import merge_dados


def executar_fluxo(params):
    logs.clear()

    modo_coleta = params["modo_coleta"]
    url_base = params["url_base"]
    arquivo_dados = params["arquivo_dados"]
    modelo_estoque_file = params["modelo_estoque_file"]
    modelo_cadastro_file = params["modelo_cadastro_file"]
    filtro = params["filtro"]
    estoque_padrao = params["estoque_padrao"]
    depositos = params["depositos"]

    if not depositos:
        st.error("Informe pelo menos um depósito.")
        return None

    if not modelo_estoque_file or not modelo_cadastro_file:
        st.error("Envie os dois modelos do Bling: estoque e cadastro.")
        return None

    modelo_est = ler_planilha(modelo_estoque_file)
    modelo_cad = ler_planilha(modelo_cadastro_file)

    if modelo_est is None or modelo_cad is None:
        st.error("Não foi possível ler um dos modelos do Bling.")
        return None

    progress = st.progress(0)

    df_planilha = pd.DataFrame()
    if modo_coleta in ["Planilha + Site", "Só Planilha"]:
        if not arquivo_dados:
            st.error("Envie a planilha de dados.")
            return None

        entrada = ler_planilha(arquivo_dados)
        if entrada is None:
            st.error("Não foi possível ler a planilha de dados.")
            return None

        df_planilha = normalizar_planilha_entrada(
            entrada,
            url_base,
            estoque_padrao,
        )

    df_site = pd.DataFrame()
    if modo_coleta in ["Planilha + Site", "Só Site"]:
        links = coletar_links_site(url_base)

        if not links and modo_coleta == "Só Site":
            st.error("Nenhum link de produto foi encontrado no site.")
            return None

        produtos = []
        if links:
            st.info(f"🔗 {len(links)} links encontrados no site")

            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = [
                    ex.submit(extrair_site, link, filtro, estoque_padrao)
                    for link in links
                ]

                total = len(links)
                for i, future in enumerate(as_completed(futures), start=1):
                    try:
                        resultado = future.result()
                        if resultado:
                            produtos.append(resultado)
                    except Exception as e:
                        logs.append(f"ERRO extrair_site: {e}")

                    progress.progress(i / total)

        df_site = pd.DataFrame(produtos)

    df = merge_dados(df_planilha, df_site, url_base, estoque_padrao)

    if df is None or df.empty:
        st.error("Nenhum dado encontrado após o processamento.")
        return None

    for col in ["Código", "Produto", "Preço", "Descrição Curta", "Imagem", "Link", "Marca", "Estoque"]:
        if col not in df.columns:
            df[col] = ""

    df["Código"] = df["Código"].fillna("").astype(str).str.strip()
    df["Produto"] = df["Produto"].fillna("").astype(str).str.strip()
    df["Preço"] = df["Preço"].fillna("0.01").astype(str).str.strip()
    df["Descrição Curta"] = df["Descrição Curta"].fillna("").astype(str).str.strip()
    df["Imagem"] = df["Imagem"].fillna("").astype(str).str.strip()
    df["Link"] = df["Link"].fillna("").astype(str).str.strip()
    df["Marca"] = df["Marca"].fillna("").astype(str).str.strip()

    df = df[df["Produto"] != ""].copy()

    if df.empty:
        st.error("Nenhum produto válido restou após a validação.")
        return None

    df_estoque = preencher_modelo_estoque(modelo_est, df, depositos)
    df_cadastro = preencher_modelo_cadastro(modelo_cad, df)

    csv_estoque = df_estoque.to_csv(index=False, sep=";", encoding="utf-8-sig")
    csv_cadastro = df_cadastro.to_csv(index=False, sep=";", encoding="utf-8-sig")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("estoque.csv", csv_estoque)
        z.writestr("cadastro.csv", csv_cadastro)
    zip_buffer.seek(0)

    return {
        "df": df,
        "df_estoque": df_estoque,
        "df_cadastro": df_cadastro,
        "csv_estoque": csv_estoque,
        "csv_cadastro": csv_cadastro,
        "zip_bytes": zip_buffer.getvalue(),
    }
