import pandas as pd
import re
import random

def limpar(txt):
    return re.sub(r"\s+", " ", str(txt)).strip()

def normalizar_planilha_entrada(df, base_url, estoque_padrao):
    out = pd.DataFrame()

    out["Código"] = df.iloc[:,0].astype(str)
    out["Produto"] = df.iloc[:,1].astype(str)

    def preco(v):
        try:
            return str(float(str(v).replace(".","").replace(",", ".")))
        except:
            return "0.01"

    out["Preço"] = df.iloc[:,2].apply(preco) if df.shape[1] > 2 else "0.01"

    out["Estoque"] = estoque_padrao
    out["Descrição Curta"] = out["Produto"]
    out["Imagem"] = ""
    out["Link"] = ""
    out["Marca"] = ""

    # CORREÇÕES
    out["Código"] = out["Código"].apply(
        lambda x: x if x.strip() else str(random.randint(1000000000000,9999999999999))
    )

    out["Produto"] = out["Produto"].replace("", "Produto sem nome")

    return out
