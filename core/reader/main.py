import pandas as pd

from core.logger import log
from core.reader.csv_reader import ler_csv
from core.reader.excel_reader import ler_excel


def _limpar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    df = df.copy()

    novas_colunas = []
    for col in df.columns:
        nome = str(col).strip()
        nome = " ".join(nome.split())
        novas_colunas.append(nome)

    df.columns = novas_colunas
    return df


def _remover_colunas_totalmente_vazias(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    return df.dropna(axis=1, how="all")


def _remover_linhas_totalmente_vazias(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    return df.dropna(axis=0, how="all")


def _normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return None

    df = _remover_colunas_totalmente_vazias(df)
    df = _remover_linhas_totalmente_vazias(df)
    df = _limpar_colunas(df)

    return df


def ler_planilha(file):
    try:
        if file is None:
            log("ler_planilha recebeu arquivo None")
            return None

        nome = (getattr(file, "name", "") or "").lower()
        log(f"Iniciando leitura do arquivo: {nome}")

        if nome.endswith(".csv"):
            df = ler_csv(file)
            return _normalizar_dataframe(df)

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            df = ler_excel(file)
            return _normalizar_dataframe(df)

        log(f"Formato não suportado: {nome}")
        return None

    except Exception as e:
        log(f"ERRO geral ler_planilha arquivo={getattr(file, 'name', 'desconhecido')} detalhe={e}")
        return None
