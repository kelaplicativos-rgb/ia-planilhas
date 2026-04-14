from __future__ import annotations

import pandas as pd

from .ia_mapper_ai import sugerir_mapeamento
from .ia_mapper_rules import aplicar_defaults


def executar_mapeamento(
    df_origem: pd.DataFrame,
    colunas_destino: list[str],
) -> pd.DataFrame:
    """
    Executa o mapeamento automático entre as colunas de origem
    e as colunas de destino do modelo.

    Mantido fiel à base atual do projeto.
    """

    if df_origem is None or df_origem.empty:
        return pd.DataFrame()

    colunas_origem = list(df_origem.columns)
    mapeamento = sugerir_mapeamento(colunas_origem, colunas_destino)

    df_saida = pd.DataFrame()

    for destino, origem in mapeamento.items():
        if origem in df_origem.columns:
            df_saida[destino] = df_origem[origem]

    df_saida = aplicar_defaults(df_saida)
    return df_saida
