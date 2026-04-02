import pandas as pd


def preencher_modelo_cadastro(modelo, df):
    mapa = {col.lower().strip(): col for col in modelo.columns}
    linhas = []

    def pegar_coluna(*nomes):
        for nome in nomes:
            nome = nome.lower().strip()
            if nome in mapa:
                return mapa[nome]
        return None

    col_codigo = pegar_coluna("código", "codigo")
    col_descricao = pegar_coluna("descrição", "descricao")
    col_tipo = pegar_coluna("tipo")
    col_situacao = pegar_coluna("situação", "situacao")
    col_unidade = pegar_coluna("unidade")
    col_preco = pegar_coluna("preço", "preco")
    col_preco_custo = pegar_coluna("preço de custo", "preco de custo")
    col_gtin = pegar_coluna("código de barras", "codigo de barras", "gtin/ean", "gtin")
    col_marca = pegar_coluna("marca")
    col_ncm = pegar_coluna("ncm")
    col_origem = pegar_coluna("origem")
    col_peso_liquido = pegar_coluna("peso líquido", "peso liquido")
    col_peso_bruto = pegar_coluna("peso bruto")
    col_estoque_minimo = pegar_coluna("estoque mínimo", "estoque minimo")
    col_estoque_maximo = pegar_coluna("estoque máximo", "estoque maximo")
    col_descricao_curta = pegar_coluna("descrição curta", "descricao curta")
    col_descricao_complementar = pegar_coluna("descrição complementar", "descricao complementar")
    col_url_imagens = pegar_coluna("url imagens externas", "url imagem", "url imagens")
    col_link_externo = pegar_coluna("link externo")

    for _, row in df.iterrows():
        nova = {col: "" for col in modelo.columns}

        if col_codigo:
            nova[col_codigo] = row.get("Código") or row.get("codigo") or row.get("SKU") or ""

        if col_descricao:
            nova[col_descricao] = row.get("Produto") or row.get("produto") or ""

        if col_tipo:
            nova[col_tipo] = "Produto"

        if col_situacao:
            nova[col_situacao] = "Ativo"

        if col_unidade:
            nova[col_unidade] = "UN"

        if col_preco:
            nova[col_preco] = row.get("Preço") or row.get("preco") or "0.01"

        if col_preco_custo:
            nova[col_preco_custo] = ""

        if col_gtin:
            nova[col_gtin] = ""

        if col_marca:
            nova[col_marca] = row.get("Marca") or row.get("marca") or ""

        if col_ncm:
            nova[col_ncm] = ""

        if col_origem:
            nova[col_origem] = "0"

        if col_peso_liquido:
            nova[col_peso_liquido] = ""

        if col_peso_bruto:
            nova[col_peso_bruto] = ""

        if col_estoque_minimo:
            nova[col_estoque_minimo] = ""

        if col_estoque_maximo:
            nova[col_estoque_maximo] = ""

        if col_descricao_curta:
            nova[col_descricao_curta] = (
                row.get("Descrição Curta")
                or row.get("descricao_curta")
                or row.get("Produto")
                or ""
            )

        if col_descricao_complementar:
            nova[col_descricao_complementar] = ""

        if col_url_imagens:
            nova[col_url_imagens] = row.get("Imagem") or row.get("imagem") or ""

        if col_link_externo:
            nova[col_link_externo] = row.get("Link") or row.get("link") or ""

        linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)
