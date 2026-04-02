import pandas as pd


def preencher_modelo_estoque(modelo, df, depositos):
    linhas = []

    mapa = {str(col).lower().strip(): col for col in modelo.columns}

    def encontrar_coluna(possiveis):
        for nome in possiveis:
            nome = nome.lower().strip()
            for col_norm, col_real in mapa.items():
                if nome == col_norm or nome in col_norm:
                    return col_real
        return None

    col_id_produto = encontrar_coluna(["id produto"])
    col_codigo = encontrar_coluna(["código produto", "codigo produto"])
    col_gtin = encontrar_coluna(["gtin"])
    col_descricao = encontrar_coluna(["descrição produto", "descricao produto"])
    col_deposito = encontrar_coluna(["depósito", "deposito"])
    col_qtd = encontrar_coluna(["balanço", "balanco", "saldo", "estoque"])
    col_preco = encontrar_coluna(["preço unitário", "preco unitario", "valor"])
    col_preco_custo = encontrar_coluna(["preço de custo", "preco de custo"])
    col_observacao = encontrar_coluna(["observação", "observacao"])
    col_data = encontrar_coluna(["data"])

    for _, row in df.iterrows():
        for deposito in depositos:
            nova = {col: "" for col in modelo.columns}

            # ID PRODUTO = sempre vazio
            if col_id_produto:
                nova[col_id_produto] = ""

            # CÓDIGO PRODUTO = SKU / código
            if col_codigo:
                nova[col_codigo] = row.get("Código", "")

            # GTIN = código de barras
            if col_gtin:
                nova[col_gtin] = row.get("GTIN", "")

            # DESCRIÇÃO PRODUTO = título
            if col_descricao:
                nova[col_descricao] = row.get("Produto", "")

            # DEPÓSITO
            if col_deposito:
                nova[col_deposito] = deposito

            # SALDO / BALANÇO
            if col_qtd:
                nova[col_qtd] = row.get("Estoque", 0)

            # PREÇO UNITÁRIO
            if col_preco:
                nova[col_preco] = row.get("Preço", "0.01")

            # PREÇO DE CUSTO = vazio
            if col_preco_custo:
                nova[col_preco_custo] = ""

            # OBSERVAÇÃO = sempre vazia
            if col_observacao:
                nova[col_observacao] = ""

            # DATA = vazia
            if col_data:
                nova[col_data] = ""

            linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)
