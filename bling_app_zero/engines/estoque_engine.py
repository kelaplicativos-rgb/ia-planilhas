from __future__ import annotations

import pandas as pd

from bling_app_zero.core.bling_models import enforce_model_contract, estoque_default_model
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping
from bling_app_zero.core.mapping_super_assistant import super_auto_map_columns
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.core.user_rules import get_user_rules, stock_defaults_from_rules


class MissingEstoqueModelError(ValueError):
    """Erro controlado quando o fluxo de estoque não tem contrato válido."""


STOCK_ALLOWED_COLUMN_HINTS = (
    'id produto',
    'idproduto',
    'produto id',
    'codigo',
    'cod',
    'sku',
    'descricao produto',
    'descricao',
    'nome produto',
    'produto',
    'deposito',
    'balanco',
    'saldo',
    'estoque',
    'quantidade',
    'qtd',
    'observacao',
    'obs',
)

STOCK_FORBIDDEN_COLUMN_HINTS = (
    'preco',
    'custo',
    'valor',
    'ncm',
    'marca',
    'categoria',
    'imagem',
    'url',
    'peso',
    'altura',
    'largura',
    'comprimento',
    'profundidade',
    'fornecedor',
)

MINIMUM_STOCK_REQUIRED_HINTS = ('balanco', 'saldo', 'estoque', 'quantidade', 'qtd')
AVAILABLE_PATTERNS = ['disponivel', 'disponível', 'em estoque', 'produto disponivel', 'produto disponível', 'in stock', 'available']
LOW_PATTERNS = ['baixo', 'baixo estoque', 'estoque baixo', 'poucas unidades', 'ultimas unidades', 'últimas unidades', 'low stock']
OUT_PATTERNS = ['esgotado', 'sem estoque', 'indisponivel', 'indisponível', 'zerado', 'out of stock', 'unavailable']


def _valid_model(df_model: pd.DataFrame | None) -> bool:
    return isinstance(df_model, pd.DataFrame) and len(df_model.columns) > 0


def _model_or_internal(df_model: pd.DataFrame | None) -> pd.DataFrame:
    if _valid_model(df_model):
        return df_model.copy().fillna('')
    return estoque_default_model()


def _is_forbidden_stock_column(column: str) -> bool:
    key = normalize_key(column)
    return any(hint in key for hint in STOCK_FORBIDDEN_COLUMN_HINTS)


def _is_allowed_stock_column(column: str) -> bool:
    key = normalize_key(column)
    if _is_forbidden_stock_column(column):
        return False
    return any(hint in key for hint in STOCK_ALLOWED_COLUMN_HINTS)


def _looks_like_stock_quantity_column(column: object) -> bool:
    key = normalize_key(column)
    return any(hint in key for hint in MINIMUM_STOCK_REQUIRED_HINTS)


def _has_stock_quantity_column(model: pd.DataFrame) -> bool:
    for column in model.columns:
        if _looks_like_stock_quantity_column(column):
            return True
    return False


def _status_to_quantity(value: object) -> str:
    text = clean_cell(value)
    if not text:
        return ''
    key = normalize_key(text)
    defaults = stock_defaults_from_rules(get_user_rules())
    if any(normalize_key(pattern) in key for pattern in OUT_PATTERNS):
        return str(defaults.get('esgotado', '0'))
    if any(normalize_key(pattern) in key for pattern in LOW_PATTERNS):
        return str(defaults.get('baixo', '0'))
    if any(normalize_key(pattern) in key for pattern in AVAILABLE_PATTERNS):
        return str(defaults.get('disponivel', '1000'))
    return text


def _normalize_stock_status_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().fillna('')
    for column in out.columns:
        if _looks_like_stock_quantity_column(column):
            out[column] = out[column].apply(_status_to_quantity)
    return out


def _protect_stock_mapping(mapping: dict[str, str], model: pd.DataFrame) -> dict[str, str]:
    """Preserva o modelo anexado/interno e bloqueia preenchimento indevido."""
    protected: dict[str, str] = {}
    for target in model.columns:
        target_text = str(target)
        protected[target_text] = str(mapping.get(target_text) or '') if _is_allowed_stock_column(target_text) else ''
    return protected


def _fill_deposito(df: pd.DataFrame, deposito: str) -> pd.DataFrame:
    out = df.copy().fillna('')
    if not deposito:
        return out
    for col in out.columns:
        key = normalize_key(col)
        if 'deposito' in key:
            out[col] = deposito
    return out


def run_estoque_engine(df_source: pd.DataFrame, df_model: pd.DataFrame | None = None, deposito: str = '') -> tuple[pd.DataFrame, dict[str, str]]:
    model = _model_or_internal(df_model)

    if not _has_stock_quantity_column(model):
        raise MissingEstoqueModelError(
            'Modelo de estoque inválido. Não encontrei coluna de saldo, balanço, estoque ou quantidade.'
        )

    source = df_source.copy().fillna('') if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    source = _normalize_stock_status_columns(source)
    raw_mapping = super_auto_map_columns(source, model)
    mapping = _protect_stock_mapping(raw_mapping, model)
    final = apply_mapping(source, model, mapping)
    final = enforce_model_contract(final, 'estoque', model)
    final = _fill_deposito(final, deposito)
    final = _normalize_stock_status_columns(final)
    final = enforce_model_contract(final, 'estoque', model)
    return sanitize_for_bling(final, operation='estoque'), mapping