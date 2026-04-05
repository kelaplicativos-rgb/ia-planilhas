from io import BytesIO

import pandas as pd


def _normalizar_header(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    if len(df.columns) > 0 and all(str(col).isdigit() for col in df.columns):
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

    df = df.fillna("").astype(str)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def ler_planilha(file):
    if file is None:
        return pd.DataFrame()

    nome = (getattr(file, "name", "") or "").lower().strip()

    if nome.endswith(".csv"):
        try:
            file.seek(0)
            df = pd.read_csv(file, dtype=str)
        except Exception:
            file.seek(0)
            df = pd.read_csv(file, dtype=str, sep=";")
        return _normalizar_header(df)

    file.seek(0)
    df = pd.read_excel(file, dtype=str)
    return _normalizar_header(df)


def limpar_valores_vazios(df):
    if df is None or df.empty:
        return pd.DataFrame()
    return df.fillna("").astype(str)


def normalizar_colunas(df):
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def df_to_excel_bytes(df):
    output = BytesIO()
    df.to_excel(output, index=False)
    return output.getvalue()
