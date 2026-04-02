import pandas as pd


def preencher_modelo_cadastro(modelo, df):
    linhas = []

    mapa = {str(col).lower().strip(): col for col in modelo.columns}

    def encontrar_coluna(possiveis):
        for nome in possiveis:
            nome = nome.lower().strip()
            for col_norm, col_real in mapa.items():
                if nome == col_norm or nome in col_norm:
                    return col_real
        return None

    col_id = encontrar_coluna(["id"])
    col_codigo = encontrar_coluna(["código", "codigo"])
    col_descricao = encontrar_coluna(["descrição", "descricao"])
    col_tipo = encontrar_coluna(["tipo"])
    col_situacao = encontrar_coluna(["situação", "situacao"])
    col_unidade = encontrar_coluna(["unidade"])
    col_preco = encontrar_coluna(["preço", "preco"])
    col_preco_custo = encontrar_coluna(["preço de custo", "preco de custo"])
    col_gtin = encontrar_coluna(["gtin", "codigo de barras", "código de barras", "gtin/ean"])
    col_marca = encontrar_coluna(["marca"])
    col_ncm = encontrar_coluna(["ncm"])
    col_origem = encontrar_coluna(["origem"])
    col_peso_liquido = encontrar_coluna(["peso líquido", "peso liquido"])
    col_peso_bruto = encontrar_coluna(["peso bruto"])
    col_estoque_minimo = encontrar_coluna(["estoque mínimo", "estoque minimo"])
    col_estoque_maximo = encontrar_coluna(["estoque máximo", "estoque maximo"])
    col_descricao_curta = encontrar_coluna(["descrição curta", "descricao curta"])
    col_descricao_complementar = encontrar_coluna(["descrição complementar", "descricao complementar"])
    col_url_imagens = encontrar_coluna(["url imagens externas", "url imagem", "url imagens"])
    col_link_externo = encontrar_coluna(["link externo", "url produto", "link produto"])

    for _, row in df.iterrows():
        nova = {col: "" for col in modelo.columns}

        if col_id:
            nova[col_id] = ""

        if col_codigo:
            nova[col_codigo] = row.get("Código", "")

        if col_descricao:
            nova[col_descricao] = row.get("Produto", "")

        if col_tipo:
            nova[col_tipo] = row.get("Tipo", "") or "Produto"

        if col_situacao:
            nova[col_situacao] = row.get("Situação", "") or "Ativo"

        if col_unidade:
            nova[col_unidade] = row.get("Unidade", "") or "UN"

        if col_preco:
            nova[col_preco] = row.get("Preço", "") or "0.01"

        if col_preco_custo:
            nova[col_preco_custo] = row.get("Preço Custo", "")

        if col_gtin:
            nova[col_gtin] = row.get("GTIN", "")

        if col_marca:
            nova[col_marca] = row.get("Marca", "")

        if col_ncm:
            nova[col_ncm] = row.get("NCM", "")

        if col_origem:
            nova[col_origem] = row.get("Origem", "") or "0"

        if col_peso_liquido:
            nova[col_peso_liquido] = row.get("Peso Líquido", "")

        if col_peso_bruto:
            nova[col_peso_bruto] = row.get("Peso Bruto", "")

        if col_estoque_minimo:
            nova[col_estoque_minimo] = row.get("Estoque Mínimo", "")

        if col_estoque_maximo:
            nova[col_estoque_maximo] = row.get("Estoque Máximo", "")

        if col_descricao_curta:
            nova[col_descricao_curta] = row.get("Descrição Curta", "")

        if col_descricao_complementar:
            nova[col_descricao_complementar] = row.get("Descrição Complementar", "")

        if col_url_imagens:
            nova[col_url_imagens] = row.get("Imagem", "")

        if col_link_externo:
            nova[col_link_externo] = row.get("Link", "")

        linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)
