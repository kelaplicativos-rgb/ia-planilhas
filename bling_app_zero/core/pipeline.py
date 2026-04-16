
import pandas as pd


def processar_precificacao(df, margem=20):
    if df is None or df.empty:
        return df

    df = df.copy()

    if "preco_custo" in df.columns:
        df["preco_venda"] = df["preco_custo"] * (1 + margem / 100)

    return df


def processar_mapeamento(df):
    if df is None or df.empty:
        return df

    df = df.copy()

    rename_map = {
        "nome": "Descrição",
        "preco_venda": "Preço de venda",
    }

    df = df.rename(columns=rename_map)

    return df


def gerar_saida_final(df):
    if df is None:
        return df

    return df.copy()
