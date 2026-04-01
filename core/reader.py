import pandas as pd

def ler_planilha(file):
    nome = file.name.lower()

    if nome.endswith(".xlsx"):
        return pd.read_excel(file)

    if nome.endswith(".xls"):
        return pd.read_excel(file)

    if nome.endswith(".csv"):
        try:
            return pd.read_csv(file, sep=";", encoding="utf-8")
        except:
            file.seek(0)
            return pd.read_csv(file, sep=None, engine="python")

    return None
