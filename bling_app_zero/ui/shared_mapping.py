from __future__ import annotations

import pandas as pd


def render_shared_cadastro_mapping(df_source: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    """Mapeador oficial compartilhado para cadastro.

    A implementação forte continua no motor que já funciona muito bem
    (`cadastro_mapping`). Este arquivo passa a ser a porta compartilhada para
    novos fluxos usarem o mesmo mapeador sem duplicar regra, widget, confiança,
    IA assistida, valor fixo, deixar vazio, padrões seguros e preview.
    """
    from bling_app_zero.ui.cadastro_mapping import render_manual_mapping

    render_manual_mapping(df_source, df_modelo)


def render_shared_stock_mapping(
    df_source: pd.DataFrame,
    df_modelo_estoque: pd.DataFrame | None,
    deposito: str,
) -> None:
    """Mapeador oficial compartilhado para estoque.

    Usa o mesmo motor potente do cadastro e só injeta a regra específica de
    estoque: depósito como valor fixo protegido nas colunas de depósito.
    """
    from bling_app_zero.ui.cadastro_mapping import render_manual_stock_mapping

    render_manual_stock_mapping(df_source, df_modelo_estoque, deposito)


__all__ = [
    'render_shared_cadastro_mapping',
    'render_shared_stock_mapping',
]
