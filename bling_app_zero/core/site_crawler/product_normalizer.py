import pandas as pd


def normalize_products(produtos):
    resultado = []

    for p in produtos:
        if not p:
            continue

        resultado.append({
            "Nome": p.get("nome", ""),
            "Preço": p.get("preco", ""),
            "SKU": p.get("sku", ""),
            "URL": p.get("url", ""),
            "Imagem": "|".join(p.get("imagens", [])),
        })

    return resultado


def to_dataframe(produtos):
    return pd.DataFrame(produtos)
