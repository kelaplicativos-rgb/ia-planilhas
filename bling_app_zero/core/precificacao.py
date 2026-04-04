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


def calcular_preco_venda(
    preco_compra: float,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
) -> float:
    base = float(preco_compra or 0.0) + float(custo_fixo or 0.0)
    total_percentual = (
        float(percentual_impostos or 0.0)
        + float(margem_lucro or 0.0)
        + float(taxa_extra or 0.0)
    ) / 100.0
    return base * (1.0 + total_percentual)
