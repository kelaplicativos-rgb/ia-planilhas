import pandas as pd

from core.logger import log


def ler_planilha(file):
    try:
        nome = (file.name or "").lower()

        if nome.endswith(".xlsx"):
            return pd.read_excel(file, engine="openpyxl")

        if nome.endswith(".xls"):
            return pd.read_excel(file, engine="xlrd")

        if nome.endswith(".csv"):
            # tentativa 1: csv comum do Brasil
            try:
                file.seek(0)
                return pd.read_csv(file, sep=";", encoding="utf-8")
            except Exception:
                pass

            # tentativa 2: separador automático
            try:
                file.seek(0)
                return pd.read_csv(file, sep=None, engine="python", encoding="utf-8")
            except Exception:
                pass

            # tentativa 3: latin1
            try:
                file.seek(0)
                return pd.read_csv(file, sep=";", encoding="latin1")
            except Exception:
                pass

            # tentativa 4: automático + latin1
            try:
                file.seek(0)
                return pd.read_csv(file, sep=None, engine="python", encoding="latin1")
            except Exception as e:
                log(f"ERRO leitura CSV arquivo={getattr(file, 'name', 'desconhecido')} detalhe={e}")
                return None

        log(f"Formato não suportado: {getattr(file, 'name', 'desconhecido')}")
        return None

    except Exception as e:
        log(f"ERRO leitura planilha arquivo={getattr(file, 'name', 'desconhecido')} detalhe={e}")
        return None
