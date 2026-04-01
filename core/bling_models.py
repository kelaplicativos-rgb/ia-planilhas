import pandas as pd

def mapear_colunas_modelo(cols):
    mapa = {}
    for col in cols:
        c = col.strip().lower()

        if "código produto" in c:
            mapa["codigo"] = col
        elif "descrição" in c:
            mapa["descricao"] = col
        elif "preço" in c:
            mapa["preco"] = col
        elif "deposito" in c or "depósito" in c:
            mapa["deposito"] = col
        elif "saldo" in c or "estoque" in c:
            mapa["estoque"] = col
        elif "url imagens" in c:
            mapa["imagem"] = col
        elif "link externo" in c:
            mapa["link"] = col

    return mapa


def preencher_modelo_estoque(modelo, df, depositos):
    mapa = mapear_colunas_modelo(modelo.columns)
    linhas = []

    for _, row in df.iterrows():
        for dep in depositos:
            nova = {col: "" for col in modelo.columns}

            if "codigo" in mapa:
                nova[mapa["codigo"]] = row["Código"]

            if "descricao" in mapa:
                nova[mapa["descricao"]] = row["Produto"]

            if "deposito" in mapa:
                nova[mapa["deposito"]] = dep

            if "estoque" in mapa:
                nova[mapa["estoque"]] = row["Estoque"]

            linhas.append(nova)

    return pd.DataFrame(linhas)


def preencher_modelo_cadastro(modelo, df):
    mapa = mapear_colunas_modelo(modelo.columns)
    linhas = []

    for _, row in df.iterrows():
        nova = {col: "" for col in modelo.columns}

        if "codigo" in mapa:
            nova[mapa["codigo"]] = row["Código"]

        if "descricao" in mapa:
            nova[mapa["descricao"]] = row["Produto"]

        if "preco" in mapa:
            nova[mapa["preco"]] = row["Preço"]

        if "imagem" in mapa:
            nova[mapa["imagem"]] = row["Imagem"]

        if "link" in mapa:
            nova[mapa["link"]] = row["Link"]

        linhas.append(nova)

    return pd.DataFrame(linhas)
