import pandas as pd
from core.utils import limpar, gerar_codigo_fallback

def normalizar_planilha_entrada(df, base_url, estoque_padrao):
    out = pd.DataFrame()

    out["Código"] = df.iloc[:,0].astype(str).apply(gerar_codigo_fallback)
    out["Produto"] = df.iloc[:,1].astype(str).apply(limpar)
    out["Preço"] = "1.00"
    out["Estoque"] = estoque_padrao
    out["Descrição Curta"] = out["Produto"]
    out["Imagem"] = ""
    out["Link"] = ""
    out["Marca"] = ""

    return out
