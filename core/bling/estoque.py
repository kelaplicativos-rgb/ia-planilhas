import pandas as pd

from core.utils import limpar


def _valor(row, campo, default=""):
    valor = row.get(campo, default)
    return "" if valor is None else valor


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
    col_codigo = encontrar_coluna(["código produto", "codigo produto", "código", "codigo"])
    col_gtin = encontrar_coluna(["gtin", "codigo de barras", "código de barras", "gtin/ean"])
    col_descricao = encontrar_coluna(["descrição produto", "descricao produto", "descrição", "descricao"])
    col_deposito = encontrar_coluna(["depósito", "deposito"])
    col_qtd = encontrar_coluna(["balanço", "balanco", "saldo", "estoque", "quantidade"])
    col_preco = encontrar_coluna(["preço unitário", "preco unitario", "valor", "preço", "preco"])
    col_preco_custo = encontrar_coluna(["preço de custo", "preco de custo"])
    col_observacao = encontrar_coluna(["observação", "observacao"])
    col_data = encontrar_coluna(["data"])

    for _, row in df.iterrows():
        codigo = limpar(_valor(row, "Código"))
        gtin = limpar(_valor(row, "GTIN"))
        produto = limpar(_valor(row, "Produto"))
        estoque = _valor(row, "Estoque", 0)
        preco = _valor(row, "Preço", "0.01")
        preco_custo = _valor(row, "Preço Custo", "")

        if not produto:
            produto = "Produto sem nome"

        for deposito in depositos:
            nova = {col: "" for col in modelo.columns}

            if col_id_produto:
                nova[col_id_produto] = ""

            if col_codigo:
                nova[col_codigo] = codigo

            if col_gtin:
                nova[col_gtin] = gtin

            if col_descricao:
                nova[col_descricao] = produto

            if col_deposito:
                nova[col_deposito] = limpar(deposito)

            if col_qtd:
                nova[col_qtd] = estoque

            if col_preco:
                nova[col_preco] = preco or "0.01"

            if col_preco_custo:
                nova[col_preco_custo] = preco_custo

            if col_observacao:
                nova[col_observacao] = ""

            if col_data:
                nova[col_data] = ""

            linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)
