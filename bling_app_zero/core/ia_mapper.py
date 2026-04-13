from __future__ import annotations

import pandas as pd

from .ia_mapper_engine import executar_mapeamento


def mapear_colunas_ia(
    df_origem: pd.DataFrame,
    colunas_destino: list[str],
) -> pd.DataFrame:
    """
    Função pública usada pelo sistema.
    NÃO alterar assinatura.
    """

    try:
        return executar_mapeamento(
            df_origem=df_origem,
            colunas_destino=colunas_destino,
        )
    except Exception:
        return pd.DataFrame()
