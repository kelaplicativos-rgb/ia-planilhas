from __future__ import annotations

import pandas as pd

from bling_app_zero.ui.shared_mapping import render_shared_stock_mapping


def render_manual_estoque_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    """Entrada oficial do mapeamento de estoque.

    O estoque usa o mapeador compartilhado, baseado no motor potente do cadastro,
    para evitar dois mapeadores evoluindo separados e quebrando comportamento.
    """
    render_shared_stock_mapping(df_source, df_modelo, deposito)


__all__ = ['render_manual_estoque_mapping']
