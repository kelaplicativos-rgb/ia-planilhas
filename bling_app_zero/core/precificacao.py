import pandas as pd


def calcular_preco_compra_automatico_df(df: pd.DataFrame) -> float:
    """
    Detecta automaticamente um preço de compra médio a partir das colunas
    mais prováveis do dataframe gerado no fluxo do sistema.
    """
    if df is None or df.empty:
        return 0.0

    colunas_prioridade = [
        "custo",
        "preco_custo",
        "custo_total_item_xml",
        "valor_unitario",
        "valor",
        "preco",
    ]

    for col in colunas_prioridade:
        if col in df.columns:
            serie = pd.to_numeric(df[col], errors="coerce").dropna()

            if not serie.empty:
                serie = serie[serie > 0]
                if not serie.empty:
                    return float(serie.mean())

    return 0.0


def calcular_preco_venda(
    preco_compra: float,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
) -> float:
    """
    Calcula preço de venda considerando:
    - preço de compra
    - impostos (%)
    - margem de lucro (%)
    - custo fixo (R$)
    - taxa extra (%)

    Fórmula:
        venda = (compra + custo_fixo) / (1 - impostos - lucro - taxa_extra)

    Se o denominador ficar inválido (<= 0), retorna 0.0
    para evitar preço incorreto ou infinito.
    """
    try:
        base = float(preco_compra or 0.0) + float(custo_fixo or 0.0)

        impostos = float(percentual_impostos or 0.0) / 100.0
        lucro = float(margem_lucro or 0.0) / 100.0
        taxa = float(taxa_extra or 0.0) / 100.0

        denominador = 1.0 - impostos - lucro - taxa

        if denominador <= 0:
            return 0.0

        resultado = base / denominador

        if resultado < 0:
            return 0.0

        return float(resultado)
    except Exception:
        return 0.0
