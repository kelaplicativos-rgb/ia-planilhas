from __future__ import annotations

import pandas as pd


def render_manual_estoque_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None, deposito: str) -> None:
    """Entrada compartilhada do mapeamento de estoque.

    O mapeador oficial e mais completo continua sendo o de cadastro. O estoque
    usa esse mesmo motor, passando apenas o depósito como valor fixo do fluxo.
    Assim, cadastro e estoque não evoluem em caminhos diferentes.
    """
    from bling_app_zero.ui.cadastro_mapping import render_manual_stock_mapping

    render_manual_stock_mapping(df_source, df_modelo, deposito)
