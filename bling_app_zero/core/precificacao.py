import pandas as pd


def _to_float(valor) -> float:
    """
    Converte valores diversos para float com tolerância a:
    - strings vazias
    - separador decimal com vírgula
    - milhares com ponto
    - símbolos monetários
    """
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        try:
            return float(valor)
        except Exception:
            return 0.0

    texto = str(valor).strip()
    if not texto:
        return 0.0

    texto = (
        texto.replace("R$", "")
        .replace("r$", "")
        .replace(" ", "")
        .replace("\u00a0", "")
    )

    # Se tiver vírgula, assume padrão BR e remove pontos de milhar.
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        # sem vírgula, tenta limpar eventual lixo mantendo ponto decimal
        texto = texto.replace(",", "")

    try:
        return float(texto)
    except Exception:
        return 0.0


def calcular_preco_compra_automatico_df(df: pd.DataFrame) -> float:
    """
    Detecta automaticamente um preço de compra médio
    a partir das colunas mais prováveis do dataframe.
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
            serie = df[col].apply(_to_float)
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


def calcular_preco_venda_df(
    df: pd.DataFrame,
    coluna_preco_base: str,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
    nome_coluna_saida: str = "preco",
    arredondar: int = 2,
) -> pd.DataFrame:
    """
    Calcula o preço de venda por linha usando a coluna de custo/preço base
    vinda da planilha do fornecedor e grava o resultado na coluna final.
    """
    if df is None:
        return pd.DataFrame()

    df_saida = df.copy()

    if coluna_preco_base not in df_saida.columns:
        if nome_coluna_saida not in df_saida.columns:
            df_saida[nome_coluna_saida] = ""
        return df_saida

    precos_base = df_saida[coluna_preco_base].apply(_to_float)

    df_saida[nome_coluna_saida] = precos_base.apply(
        lambda valor: round(
            calcular_preco_venda(
                preco_compra=valor,
                percentual_impostos=percentual_impostos,
                margem_lucro=margem_lucro,
                custo_fixo=custo_fixo,
                taxa_extra=taxa_extra,
            ),
            arredondar,
        )
        if _to_float(valor) > 0
        else 0.0
    )

    return df_saida
