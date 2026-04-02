import pandas as pd

from core.logger import log


def ler_excel(file):
    nome = (file.name or "").lower()

    try:
        if nome.endswith(".xlsx"):
            return pd.read_excel(file, engine="openpyxl")

        if nome.endswith(".xls"):
            return pd.read_excel(file, engine="xlrd")

        return None
    except Exception as e:
        log(f"ERRO leitura Excel arquivo={getattr(file, 'name', 'desconhecido')} detalhe={e}")
        return None
