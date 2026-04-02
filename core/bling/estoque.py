import pandas as pd


def preencher_modelo_estoque(modelo, df, depositos):
    linhas = []

    # 🔥 normaliza colunas do modelo
    mapa = {col.lower().strip(): col for col in modelo.columns}

    def encontrar_coluna(possiveis):
        for nome in possiveis:
            nome = nome.lower().strip()
            for col_norm, col_real in mapa.items():
                if nome in col_norm:
                    return col_real
        return None

    # 🔥 DETECÇÃO FLEXÍVEL (ESSA É A CORREÇÃO)
    col_codigo = encontrar_coluna(["codigo", "código"])
    col_produto = encontrar_coluna(["descricao", "produto"])
    col_deposito = encontrar_coluna(["deposito", "depósito"])
    col_qtd = encontrar_coluna(["saldo", "balanco", "balanço", "estoque"])
    col_preco = encontrar_coluna(["preco", "preço", "valor"])
    col_obs = encontrar_coluna(["observacao", "observação"])

    for _, row in df.iterrows():
        for deposito in depositos:

            nova = {col: "" for col in modelo.columns}

            # 🔥 PREENCHIMENTO FORÇADO
            if col_codigo:
                nova[col_codigo] = row.get("Código", "")

            if col_produto:
                nova[col_produto] = row.get("Produto", "")

            if col_deposito:
                nova[col_deposito] = deposito

            if col_qtd:
                nova[col_qtd] = row.get("Estoque", 0)

            if col_preco:
                nova[col_preco] = row.get("Preço", "0.01")

            if col_obs:
                nova[col_obs] = row.get("Descrição Curta", "")

            linhas.append(nova)

    df_final = pd.DataFrame(linhas, columns=modelo.columns)

    return df_final
