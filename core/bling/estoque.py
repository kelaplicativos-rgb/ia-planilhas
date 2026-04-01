import pandas as pd
from core.bling.mapper import mapear_colunas_modelo


def preencher_modelo_estoque(modelo, df, depositos):
    mapa = mapear_colunas_modelo(list(modelo.columns))
    linhas = []

    for _, row in df.iterrows():
        for deposito in depositos:
            nova = {col: "" for col in modelo.columns}

            if "estoque_id_produto" in mapa:
                nova[mapa["estoque_id_produto"]] = ""

            if "estoque_codigo" in mapa:
                nova[mapa["estoque_codigo"]] = row.get("Código", "")

            if "estoque_gtin" in mapa:
                nova[mapa["estoque_gtin"]] = ""

            if "estoque_descricao" in mapa:
                nova[mapa["estoque_descricao"]] = row.get("Produto", "")

            if "estoque_deposito" in mapa:
                nova[mapa["estoque_deposito"]] = deposito

            if "estoque_qtd" in mapa:
                nova[mapa["estoque_qtd"]] = row.get("Estoque", 0)

            if "estoque_preco" in mapa:
                nova[mapa["estoque_preco"]] = row.get("Preço", "0.01")

            if "estoque_preco_custo" in mapa:
                nova[mapa["estoque_preco_custo"]] = ""

            if "estoque_observacao" in mapa:
                nova[mapa["estoque_observacao"]] = ""

            if "estoque_data" in mapa:
                nova[mapa["estoque_data"]] = ""

            linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)
