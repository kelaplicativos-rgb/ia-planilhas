from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from bling_app_zero.core.shared_price_calculator import (
    PRICE_OUTPUT_COLUMN,
    PROMO_PRICE_OUTPUT_COLUMN,
    apply_shared_pricing,
    normalize_shared_price_config,
)

PRICE_TARGET_ALIASES = [
    PRICE_OUTPUT_COLUMN,
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Preco',
    'Valor',
]
PROMO_PRICE_TARGET_ALIASES = [
    PROMO_PRICE_OUTPUT_COLUMN,
    'Preco Promocional',
    'Preço Promocional',
    'Preço promocional',
    'preco_promocional',
    'preço_promocional',
]

COST_STRONG_TERMS = [
    'preço custo',
    'preco custo',
    'valor custo',
    'custo',
    'cost',
    'preco compra',
    'preço compra',
    'valor compra',
]
COST_WEAK_TERMS = ['valor produto', 'valor', 'preço', 'preco', 'price']
BAD_COST_TERMS = ['venda', 'unitario', 'unitário', 'marketplace', 'comissao', 'comissão', 'taxa', 'lucro', 'promocional']


@dataclass(frozen=True)
class PricePluginResult:
    df: pd.DataFrame
    applied: bool
    source_column: str = ''
    output_column: str = PRICE_OUTPUT_COLUMN
    promo_output_column: str = PROMO_PRICE_OUTPUT_COLUMN
    message: str = ''


def _column_score_for_cost(column: str) -> int:
    text = str(column or '').lower()
    score = 0
    for term in COST_STRONG_TERMS:
        if term in text:
            score += 100
    for term in COST_WEAK_TERMS:
        if term in text:
            score += 35
    for term in BAD_COST_TERMS:
        if term in text:
            score -= 60
    return score


def best_cost_column(columns: Iterable[str]) -> str:
    normalized = [str(column) for column in columns]
    if not normalized:
        return ''
    scored = [(column, _column_score_for_cost(column)) for column in normalized]
    best_column, best_score = max(scored, key=lambda item: item[1])
    return best_column if best_score > 0 else normalized[0]


def apply_price_aliases(df: pd.DataFrame, calculated_column: str = PRICE_OUTPUT_COLUMN, aliases: Iterable[str] | None = None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or calculated_column not in df.columns:
        return df
    out = df.copy().fillna('')
    calculated_values = out[calculated_column]
    for column in list(aliases or PRICE_TARGET_ALIASES):
        out[str(column)] = calculated_values
    return out


def apply_promotional_price_aliases(
    df: pd.DataFrame,
    calculated_column: str = PROMO_PRICE_OUTPUT_COLUMN,
    aliases: Iterable[str] | None = None,
) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or calculated_column not in df.columns:
        return df
    out = df.copy().fillna('')
    calculated_values = out[calculated_column]
    for column in list(aliases or PROMO_PRICE_TARGET_ALIASES):
        out[str(column)] = calculated_values
    return out


def apply_price_calculator_plugin(
    df: pd.DataFrame,
    *,
    enabled: bool,
    config: dict[str, Any] | None,
    cost_column: str | None = None,
    output_column: str = PRICE_OUTPUT_COLUMN,
    channel: str = 'shared_price_plugin',
    aliases: Iterable[str] | None = None,
    promo_output_column: str = PROMO_PRICE_OUTPUT_COLUMN,
    promo_aliases: Iterable[str] | None = None,
) -> PricePluginResult:
    """Aplica a calculadora como plugin universal.

    Contrato do plugin:
    - não pertence a cadastro, estoque ou atualização de preços;
    - recebe DataFrame, configuração, coluna de custo e canal lógico;
    - se `enabled` for falso, devolve a origem intacta;
    - se `cost_column` não vier, detecta a melhor coluna de custo;
    - cria uma coluna de preço de venda, uma de preço promocional e aliases opcionais para facilitar mapeamento.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return PricePluginResult(df=df, applied=False, message='Origem vazia ou inválida.')

    out = df.copy().fillna('')
    normalized_config = normalize_shared_price_config(config)
    if not enabled or not bool(normalized_config.get('enabled', False)):
        return PricePluginResult(df=out, applied=False, message='Calculadora desativada.')

    columns = [str(column) for column in out.columns]
    selected_cost_column = str(cost_column or '').strip() or best_cost_column(columns)
    if not selected_cost_column or selected_cost_column not in out.columns:
        return PricePluginResult(df=out, applied=False, message='Coluna de custo não encontrada.')

    priced = apply_shared_pricing(
        out,
        cost_column=selected_cost_column,
        output_column=output_column,
        config=normalized_config,
        channel=channel,
        promo_output_column=promo_output_column,
    )
    priced = apply_price_aliases(priced, output_column, aliases)
    priced = apply_promotional_price_aliases(priced, promo_output_column, promo_aliases)
    return PricePluginResult(
        df=priced,
        applied=True,
        source_column=selected_cost_column,
        output_column=output_column,
        promo_output_column=promo_output_column,
        message=f'Calculadora aplicada usando a coluna "{selected_cost_column}".',
    )


__all__ = [
    'PRICE_OUTPUT_COLUMN',
    'PRICE_TARGET_ALIASES',
    'PROMO_PRICE_OUTPUT_COLUMN',
    'PROMO_PRICE_TARGET_ALIASES',
    'PricePluginResult',
    'apply_price_aliases',
    'apply_price_calculator_plugin',
    'apply_promotional_price_aliases',
    'best_cost_column',
]
