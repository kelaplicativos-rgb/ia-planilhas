import pandas as pd
from io import BytesIO


def ler_planilha(file):
    df = pd.read_excel(file, dtype=str)

    # 🔥 CORREÇÃO CRÍTICA: detectar header errado
    if all(str(col).isdigit() for col in df.columns):
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)

    df = df.fillna("").astype(str)
    df.columns = [str(c).strip() for c in df.columns]

    return df


def limpar_valores_vazios(df):
    return df.fillna("").astype(str)


def normalizar_colunas(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df


def df_to_excel_bytes(df):
    output = BytesIO()
    df.to_excel(output, index=False)
    return output.getvalue()
