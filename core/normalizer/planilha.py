import pandas as pd
import re


# =========================
# HELPERS
# =========================
def limpar_texto(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def limpar_preco(valor):
    if pd.isna(valor):
        return "0.01"

    valor = str(valor)

    valor = valor.replace("R$", "")
    valor = valor.replace(".", "")
    valor = valor.replace(",", ".")

    valor = re.sub(r"[^\d\.]", "", valor)

    try:
        return str(float(valor))
    except:
        return "0.01"


def extrair_codigo(row):
    for col in row.index:
        val = str(row[col])

        # pega código grande (SKU real)
        match = re.search(r"\d{8,14}", val)
        if match:
            return match.group()

    return ""


# =========================
# DETECÇÃO INTELIGENTE
# =========================
def detectar_colunas(df):
    mapa = {}

    for col in df.columns:
        nome = col.lower()

        if "nome" in nome or "produto" in nome:
            mapa["Produto"] = col

        elif "preço" in nome or "valor" in nome:
            mapa["Preço"] = col

        elif "código" in nome or "sku" in nome:
            mapa["Código"] = col

        elif "marca" in nome:
            mapa["Marca"] = col

        elif "descricao" in nome:
            mapa["Descrição Curta"] = col

        elif "imagem" in nome:
            mapa["Imagem"] = col

        elif "link" in nome or "url" in nome:
            mapa["Link"] = col

        elif "gtin" in nome or "ean" in nome:
            mapa["GTIN"] = col

        elif "ncm" in nome:
            mapa["NCM"] = col

    return mapa


# =========================
# NORMALIZAÇÃO PRINCIPAL
# =========================
def normalizar_planilha_entrada(df, url_base="", estoque_padrao=10):

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # limpa nomes colunas
    df.columns = [str(c).strip() for c in df.columns]

    mapa = detectar_colunas(df)

    dados = []

    for _, row in df.iterrows():

        codigo = ""
        if "Código" in mapa:
            codigo = limpar_texto(row[mapa["Código"]])
        if not codigo:
            codigo = extrair_codigo(row)

        produto = limpar_texto(row[mapa["Produto"]]) if "Produto" in mapa else ""

        preco = limpar_preco(row[mapa["Preço"]]) if "Preço" in mapa else "0.01"

        marca = limpar_texto(row[mapa["Marca"]]) if "Marca" in mapa else ""

        descricao = (
            limpar_texto(row[mapa["Descrição Curta"]])
            if "Descrição Curta" in mapa
            else produto
        )

        imagem = limpar_texto(row[mapa["Imagem"]]) if "Imagem" in mapa else ""

        link = limpar_texto(row[mapa["Link"]]) if "Link" in mapa else ""

        gtin = limpar_texto(row[mapa["GTIN"]]) if "GTIN" in mapa else ""

        ncm = limpar_texto(row[mapa["NCM"]]) if "NCM" in mapa else ""

        dados.append(
            {
                "Código": codigo,
                "Produto": produto,
                "Preço": preco,
                "Descrição Curta": descricao if descricao else produto,
                "Imagem": imagem,
                "Link": link,
                "Marca": marca,
                "GTIN": gtin,
                "NCM": ncm,
                "Estoque": estoque_padrao,
            }
        )

    df_final = pd.DataFrame(dados)

    # remove lixo
    df_final = df_final[df_final["Produto"] != ""].copy()

    # remove duplicados por código
    if "Código" in df_final.columns:
        df_final = df_final.drop_duplicates(subset=["Código"])

    return df_final.reset_index(drop=True)
