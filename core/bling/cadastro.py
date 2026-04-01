import pandas as pd
from core.bling.mapper import mapear_colunas_modelo


def preencher_modelo_cadastro(modelo, df):
    mapa = mapear_colunas_modelo(list(modelo.columns))
    linhas = []

    for _, row in df.iterrows():
        nova = {col: "" for col in modelo.columns}

        if "cadastro_codigo" in mapa:
            nova[mapa["cadastro_codigo"]] = row.get("Código", "")

        if "cadastro_descricao" in mapa:
            nova[mapa["cadastro_descricao"]] = row.get("Produto", "")

        if "cadastro_tipo" in mapa:
            nova[mapa["cadastro_tipo"]] = "Produto"

        if "cadastro_situacao" in mapa:
            nova[mapa["cadastro_situacao"]] = "Ativo"

        if "cadastro_unidade" in mapa:
            nova[mapa["cadastro_unidade"]] = "UN"

        if "cadastro_preco" in mapa:
            nova[mapa["cadastro_preco"]] = row.get("Preço", "0.01")

        if "cadastro_preco_custo" in mapa:
            nova[mapa["cadastro_preco_custo"]] = ""

        if "cadastro_gtin" in mapa:
            nova[mapa["cadastro_gtin"]] = ""

        if "cadastro_marca" in mapa:
            nova[mapa["cadastro_marca"]] = row.get("Marca", "")

        if "cadastro_ncm" in mapa:
            nova[mapa["cadastro_ncm"]] = ""

        if "cadastro_origem" in mapa:
            nova[mapa["cadastro_origem"]] = "0"

        if "cadastro_peso_liquido" in mapa:
            nova[mapa["cadastro_peso_liquido"]] = ""

        if "cadastro_peso_bruto" in mapa:
            nova[mapa["cadastro_peso_bruto"]] = ""

        if "cadastro_estoque_minimo" in mapa:
            nova[mapa["cadastro_estoque_minimo"]] = ""

        if "cadastro_estoque_maximo" in mapa:
            nova[mapa["cadastro_estoque_maximo"]] = ""

        if "cadastro_descricao_curta" in mapa:
            nova[mapa["cadastro_descricao_curta"]] = row.get("Descrição Curta", "")

        if "cadastro_descricao_complementar" in mapa:
            nova[mapa["cadastro_descricao_complementar"]] = ""

        if "cadastro_url_imagens" in mapa:
            nova[mapa["cadastro_url_imagens"]] = row.get("Imagem", "")

        if "cadastro_link_externo" in mapa:
            nova[mapa["cadastro_link_externo"]] = row.get("Link", "")

        linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)
