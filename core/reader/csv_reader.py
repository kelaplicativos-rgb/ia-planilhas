import pandas as pd

from core.logger import log


def ler_csv(file):
    tentativas = [
        {"sep": ";", "encoding": "utf-8"},
        {"sep": ";", "encoding": "utf-8-sig"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": None, "engine": "python", "encoding": "utf-8"},
        {"sep": None, "engine": "python", "encoding": "utf-8-sig"},
        {"sep": None, "engine": "python", "encoding": "latin1"},
        {"sep": ",", "encoding": "utf-8"},
        {"sep": ",", "encoding": "utf-8-sig"},
        {"sep": ",", "encoding": "latin1"},
        {"sep": "\t", "encoding": "utf-8"},
        {"sep": "\t", "encoding": "latin1"},
    ]

    for i, tentativa in enumerate(tentativas, start=1):
        try:
            file.seek(0)
            df = pd.read_csv(file, **tentativa)

            if df is not None and not df.empty and len(df.columns) > 0:
                log(f"CSV lido com sucesso na tentativa {i}: {tentativa}")
                return df

        except Exception as e:
            log(f"CSV tentativa {i} falhou: {tentativa} | detalhe={e}")

    log(f"ERRO leitura CSV arquivo={getattr(file, 'name', 'desconhecido')}")
    return None
