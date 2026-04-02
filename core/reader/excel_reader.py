import pandas as pd

from core.logger import log


def ler_excel(file):
    nome = (getattr(file, "name", "") or "").lower()

    motores = []

    if nome.endswith(".xlsx"):
        motores = ["openpyxl"]

    elif nome.endswith(".xls"):
        motores = ["xlrd"]

    else:
        motores = ["openpyxl", "xlrd"]

    for i, engine in enumerate(motores, start=1):
        try:
            file.seek(0)
            df = pd.read_excel(file, engine=engine)

            if df is not None and not df.empty and len(df.columns) > 0:
                log(f"Excel lido com sucesso na tentativa {i} com engine={engine}")
                return df

        except Exception as e:
            log(f"Excel tentativa {i} falhou com engine={engine} | detalhe={e}")

    log(f"ERRO leitura Excel arquivo={getattr(file, 'name', 'desconhecido')}")
    return None
