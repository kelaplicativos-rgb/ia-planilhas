import pandas as pd

from core.logger import log


def ler_csv(file):
    # tentativa 1: csv Brasil
    try:
        file.seek(0)
        return pd.read_csv(file, sep=";", encoding="utf-8")
    except Exception:
        pass

    # tentativa 2: separador automático utf-8
    try:
        file.seek(0)
        return pd.read_csv(file, sep=None, engine="python", encoding="utf-8")
    except Exception:
        pass

    # tentativa 3: brasil latin1
    try:
        file.seek(0)
        return pd.read_csv(file, sep=";", encoding="latin1")
    except Exception:
        pass

    # tentativa 4: automático latin1
    try:
        file.seek(0)
        return pd.read_csv(file, sep=None, engine="python", encoding="latin1")
    except Exception as e:
        log(f"ERRO leitura CSV arquivo={getattr(file, 'name', 'desconhecido')} detalhe={e}")
        return None
