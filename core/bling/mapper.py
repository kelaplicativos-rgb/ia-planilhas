def mapear_colunas_modelo(cols):
    mapa = {}

    for col in cols:
        c = str(col).strip().lower()

        # ESTOQUE
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

        # CADASTRO
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
