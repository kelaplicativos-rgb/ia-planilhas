import pandas as pd


# ==========================================================
# BASE
# ==========================================================
def _to_float(valor) -> float:
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

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", "")

    try:
        return float(texto)
    except Exception:
        return 0.0


# ==========================================================
# DETECÇÃO AUTOMÁTICA DE COLUNA DE CUSTO
# ==========================================================
def _detectar_coluna_preco(df: pd.DataFrame) -> str:
    prioridades = [
        "preco custo",
        "preço custo",
        "custo",
        "valor custo",
        "preco_compra",
        "preço compra",
        "valor_unitario",
    ]

    for col in df.columns:
        nome = str(col).lower()
        for alvo in prioridades:
            if alvo in nome:
                return col

    return ""


# ==========================================================
# DETECTAR COLUNA DE VENDA
# ==========================================================
def _detectar_coluna_venda(df: pd.DataFrame) -> str:
    for col in df.columns:
        nome = str(col).lower()
        if "preço de venda" in nome or "preco de venda" in nome:
            return col

    return ""


# ==========================================================
# CÁLCULO BASE
# ==========================================================
def calcular_preco_venda(
    preco_compra: float,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
) -> float:
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


# ==========================================================
# APLICAÇÃO AUTOMÁTICA NO DF (🔥 CORRIGIDO)
# ==========================================================
def aplicar_precificacao_automatica(
    df: pd.DataFrame,
    coluna_preco: str = None,  # 🔥 NOVO
    percentual_impostos: float = 0.0,
    margem_lucro: float = 0.0,
    custo_fixo: float = 0.0,
    taxa_extra: float = 0.0,
) -> pd.DataFrame:

    if df is None or df.empty:
        return df

    df_saida = df.copy()

    # 🔥 PRIORIDADE: usar coluna vinda da UI
    if coluna_preco and coluna_preco in df_saida.columns:
        coluna_base = coluna_preco
    else:
        coluna_base = _detectar_coluna_preco(df_saida)

    if not coluna_base:
        return df_saida

    precos_base = df_saida[coluna_base].apply(_to_float)

    # 🔥 garantir coluna padrão Bling
    coluna_destino = _detectar_coluna_venda(df_saida)

    if not coluna_destino:
        coluna_destino = "Preço de venda"
        df_saida[coluna_destino] = 0.0

    # 🔥 cálculo
    df_saida[coluna_destino] = precos_base.apply(
        lambda valor: round(
            calcular_preco_venda(
                preco_compra=valor,
                percentual_impostos=percentual_impostos,
                margem_lucro=margem_lucro,
                custo_fixo=custo_fixo,
                taxa_extra=taxa_extra,
            ),
            2,
        )
        if _to_float(valor) > 0
        else 0.0
    )

    return df_saida


# ==========================================================
# COMPATIBILIDADE ANTIGA
# ==========================================================
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

    if df is None:
        return pd.DataFrame()

    df_saida = df.copy()

    if coluna_preco_base not in df_saida.columns:
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
