import pandas as pd


def preencher_modelo_estoque(modelo, df, depositos):
    mapa = {col.lower().strip(): col for col in modelo.columns}
    linhas = []

    def pegar_coluna(*nomes):
        for nome in nomes:
            nome = nome.lower().strip()
            if nome in mapa:
                return mapa[nome]
        return None

    col_id_produto = pegar_coluna("id produto")
    col_codigo = pegar_coluna("código produto", "codigo produto")
    col_gtin = pegar_coluna("gtin")
    col_descricao = pegar_coluna("descrição produto", "descricao produto")
    col_deposito = pegar_coluna("depósito", "deposito")
    col_qtd = pegar_coluna("balanço", "balanco", "saldo", "estoque")
    col_preco = pegar_coluna("preço unitário", "preco unitario", "valor")
    col_preco_custo = pegar_coluna("preço de custo", "preco de custo")
    col_observacao = pegar_coluna("observação", "observacao")
    col_data = pegar_coluna("data")

    for _, row in df.iterrows():
        for deposito in depositos:
            nova = {col: "" for col in modelo.columns}

            if col_id_produto:
                nova[col_id_produto] = ""

            if col_codigo:
                nova[col_codigo] = row.get("Código") or row.get("codigo") or row.get("SKU") or ""

            if col_gtin:
                nova[col_gtin] = ""

            if col_descricao:
                nova[col_descricao] = row.get("Produto") or row.get("produto") or ""

            if col_deposito:
                nova[col_deposito] = deposito

            if col_qtd:
                nova[col_qtd] = row.get("Estoque") or row.get("estoque") or 0

            if col_preco:
                nova[col_preco] = row.get("Preço") or row.get("preco") or "0.01"

            if col_preco_custo:
                nova[col_preco_custo] = ""

            if col_observacao:
                nova[col_observacao] = ""

            if col_data:
                nova[col_data] = ""

            linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)
