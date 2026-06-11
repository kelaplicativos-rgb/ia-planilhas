from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/product_pricing_center.py'

PRICE_COLUMNS = ['Preço unitário (OBRIGATÓRIO)', 'Preço unitário', 'Preco unitario', 'Preço', 'Preco', 'price', 'valor']
COST_COLUMNS = ['Preço de compra', 'Preco de compra', 'Preço custo', 'Preco custo', 'Custo', 'custo', 'valor custo']


@dataclass(frozen=True)
class PricingConfig:
    impostos_percentual: float = 0.0
    margem_percentual: float = 0.0
    custo_fixo: float = 0.0
    taxa_extra: float = 0.0
    casas_decimais: int = 2

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'PricingConfig':
        data = dict(values or {})
        return cls(
            impostos_percentual=to_float(data.get('impostos_percentual', data.get('impostos', 0))),
            margem_percentual=to_float(data.get('margem_percentual', data.get('margem', 0))),
            custo_fixo=to_float(data.get('custo_fixo', data.get('fixo', 0))),
            taxa_extra=to_float(data.get('taxa_extra', data.get('taxa', 0))),
            casas_decimais=int(data.get('casas_decimais', 2) or 2),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace('R$', '').replace('%', '').replace(' ', '')
    if not text or text.lower() in {'nan', 'none', 'null'}:
        return default
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    else:
        text = text.replace(',', '.')
    try:
        return float(text)
    except Exception:
        return default


def format_money(value: Any, casas_decimais: int = 2) -> str:
    return f'{to_float(value):.{int(casas_decimais or 2)}f}'.replace('.', ',')


def calculate_price(custo_base: Any, config: PricingConfig | Mapping[str, Any] | None = None, **kwargs: Any) -> float:
    cfg = config if isinstance(config, PricingConfig) else PricingConfig.from_mapping(config)
    if kwargs:
        data = cfg.to_dict()
        data.update(kwargs)
        cfg = PricingConfig.from_mapping(data)
    custo = max(to_float(custo_base), 0.0)
    subtotal = custo + max(cfg.custo_fixo, 0.0) + max(cfg.taxa_extra, 0.0)
    subtotal += custo * (max(cfg.impostos_percentual, 0.0) / 100.0)
    total = subtotal + subtotal * (max(cfg.margem_percentual, 0.0) / 100.0)
    return round(total, max(int(cfg.casas_decimais or 2), 0))


def calcular_preco(custo_base: Any, config: PricingConfig | Mapping[str, Any] | None = None, **kwargs: Any) -> float:
    return calculate_price(custo_base, config, **kwargs)


def calculate_price_from_percentages(custo_base: Any, impostos_percentual: Any = 0, margem_percentual: Any = 0, custo_fixo: Any = 0, taxa_extra: Any = 0) -> float:
    return calculate_price(custo_base, PricingConfig(to_float(impostos_percentual), to_float(margem_percentual), to_float(custo_fixo), to_float(taxa_extra)))


def find_first_column(df: pd.DataFrame, candidates: list[str]) -> str:
    if not isinstance(df, pd.DataFrame):
        return ''
    cols = [str(c) for c in df.columns]
    lowered = {c.lower().strip(): c for c in cols}
    for candidate in candidates:
        if str(candidate).lower().strip() in lowered:
            return lowered[str(candidate).lower().strip()]
    for col in cols:
        key = col.lower().strip()
        if any(str(candidate).lower().strip() in key for candidate in candidates):
            return col
    return ''


def detect_cost_column(df: pd.DataFrame) -> str:
    return find_first_column(df, COST_COLUMNS + PRICE_COLUMNS)


def detect_price_column(df: pd.DataFrame) -> str:
    return find_first_column(df, PRICE_COLUMNS)


def apply_pricing_to_dataframe(df: pd.DataFrame, config: PricingConfig | Mapping[str, Any] | None = None, *, cost_column: str | None = None, price_column: str | None = None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    out = df.copy()
    cfg = config if isinstance(config, PricingConfig) else PricingConfig.from_mapping(config)
    origem = cost_column or detect_cost_column(out)
    destino = price_column or detect_price_column(out) or 'Preço unitário (OBRIGATÓRIO)'
    if destino not in out.columns:
        out[destino] = ''
    if origem and origem in out.columns:
        out[destino] = [format_money(calculate_price(v, cfg), cfg.casas_decimais) for v in out[origem].tolist()]
    return out.fillna('')


apply_pricing = apply_pricing_to_dataframe
precificar_dataframe = apply_pricing_to_dataframe
calcular_preco_olist = calculate_price_from_percentages
price_with_margin = calculate_price_from_percentages
reprice_dataframe = apply_pricing_to_dataframe
apply_calculator_to_dataframe = apply_pricing_to_dataframe

__all__ = [
    'PricingConfig', 'PRICE_COLUMNS', 'COST_COLUMNS', 'to_float', 'format_money',
    'calculate_price', 'calcular_preco', 'calculate_price_from_percentages',
    'calcular_preco_olist', 'price_with_margin', 'find_first_column',
    'detect_cost_column', 'detect_price_column', 'apply_pricing_to_dataframe',
    'apply_pricing', 'precificar_dataframe', 'reprice_dataframe', 'apply_calculator_to_dataframe',
]
