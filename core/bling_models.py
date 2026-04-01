import pandas as pd


def mapear_colunas_modelo(cols):
    mapa = {}

    for col in cols:
        c = str(col).strip().lower()

        # =========================
        # ESTOQUE
        # =========================
        if "id produto" in c:
            mapa["estoque_id_produto"] = col
        elif "código produto" in c or "codigo produto" in c:
            mapa["estoque_codigo"] = col
        elif c == "gtin":
            mapa["estoque_gtin"] = col
        elif "descrição produto" in c or "descricao produto" in c:
            mapa["estoque_descricao"] = col
        elif "deposito" in c or "depósito" in c:
            mapa["estoque_deposito"] = col
        elif "balanço" in c or "balanco" in c or c == "saldo" or c == "estoque":
            mapa["estoque_qtd"] = col
        elif "preço unitário" in c or "preco unitario" in c or c == "valor":
            mapa["estoque_preco"] = col
        elif "preço de custo" in c or "preco de custo" in c:
            mapa["estoque_preco_custo"] = col
        elif "observação" in c or "observacao" in c:
            mapa["estoque_observacao"] = col
        elif c == "data":
            mapa["estoque_data"] = col

        # =========================
        # CADASTRO
        # =========================
        elif c == "código" or c == "codigo":
            mapa["cadastro_codigo"] = col
        elif c == "descrição" or c == "descricao":
            mapa["cadastro_descricao"] = col
        elif c == "tipo":
            mapa["cadastro_tipo"] = col
        elif "situação" in c or "situacao" in c:
            mapa["cadastro_situacao"] = col
        elif "unidade" in c:
            mapa["cadastro_unidade"] = col
        elif c == "preço" or c == "preco":
            mapa["cadastro_preco"] = col
        elif "preço de custo" in c or "preco de custo" in c:
            mapa["cadastro_preco_custo"] = col
        elif "código de barras" in c or "codigo de barras" in c or "gtin/ean" in c:
            mapa["cadastro_gtin"] = col
        elif c == "marca":
            mapa["cadastro_marca"] = col
        elif c == "ncm":
            mapa["cadastro_ncm"] = col
        elif c == "origem":
            mapa["cadastro_origem"] = col
        elif "peso líquido" in c or "peso liquido" in c:
            mapa["cadastro_peso_liquido"] = col
        elif "peso bruto" in c:
            mapa["cadastro_peso_bruto"] = col
        elif "estoque mínimo" in c or "estoque minimo" in c:
            mapa["cadastro_estoque_minimo"] = col
        elif "estoque máximo" in c or "estoque maximo" in c:
            mapa["cadastro_estoque_maximo"] = col
        elif "descrição curta" in c or "descricao curta" in c:
            mapa["cadastro_descricao_curta"] = col
        elif "descrição complementar" in c or "descricao complementar" in c:
            mapa["cadastro_descricao_complementar"] = col
        elif "url imagens externas" in c or "url imagem" in c or "url imagens" in c:
            mapa["cadastro_url_imagens"] = col
        elif "link externo" in c:
            mapa["cadastro_link_externo"] = col

    return mapa


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


def preencher_modelo_cadastro(modelo, df):
    mapa = mapear_colunas_modelo(list(modelo.columns))
    linhas = []

    for _, row in df.iterrows():
        nova = {col: "" for col in modelo.columns}

        # CÓDIGO / SKU
        if "cadastro_codigo" in mapa:
            nova[mapa["cadastro_codigo"]] = row.get("Código", "")

        # DESCRIÇÃO PRINCIPAL
        if "cadastro_descricao" in mapa:
            nova[mapa["cadastro_descricao"]] = row.get("Produto", "")

        # CAMPOS PADRÃO
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

        # DESCRIÇÃO CURTA
        if "cadastro_descricao_curta" in mapa:
            nova[mapa["cadastro_descricao_curta"]] = row.get("Descrição Curta", "")

        # DESCRIÇÃO COMPLEMENTAR VAZIA
        if "cadastro_descricao_complementar" in mapa:
            nova[mapa["cadastro_descricao_complementar"]] = ""

        # IMAGEM
        if "cadastro_url_imagens" in mapa:
            nova[mapa["cadastro_url_imagens"]] = row.get("Imagem", "")

        # LINK EXTERNO
        if "cadastro_link_externo" in mapa:
            nova[mapa["cadastro_link_externo"]] = row.get("Link", "")

        linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)
