from __future__ import annotations

import pandas as pd

from bling_app_zero.ui.cadastro_pricing import (
    PRICE_TARGET_ALIASES,
    apply_calculated_price_aliases,
    best_cost_column,
    render_cadastro_pricing,
)


def render_shared_pricing(df_origem: pd.DataFrame, *, channel: str = 'cadastro_estoque') -> pd.DataFrame:
    """Aplica a calculadora compartilhada sem amarrar o nome ao fluxo de cadastro.

    Mantém compatibilidade com o motor existente e deixa claro para as telas de
    cadastro, estoque, preço e multilojas que a precificação é um serviço comum.
    """
    return render_cadastro_pricing(df_origem, channel=channel)


__all__ = [
    'PRICE_TARGET_ALIASES',
    'apply_calculated_price_aliases',
    'best_cost_column',
    'render_shared_pricing',
]
