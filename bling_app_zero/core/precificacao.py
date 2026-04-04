import pandas as pd


def calcular_preco_compra_automatico_df(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 0.0

    colunas_prioridade = [
        "preco_custo",
        "custo_total_item_xml",
        "preco",
    ]

    for col in colunas_prioridade:
        if col in df.columns:
            serie = pd.to_numeric(df[col], errors="coerce").fillna(0)
            valor = float(serie.mean()) if len(serie) > 0 else 0.0
            if valor > 0:
                return valor

    return 0.0
