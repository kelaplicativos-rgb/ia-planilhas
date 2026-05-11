from __future__ import annotations

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.mapping import apply_mapping
from bling_app_zero.core.mapping_super_assistant import super_auto_map_columns
from bling_app_zero.core.text import normalize_key


class MissingEstoqueModelError(ValueError):
    """Erro controlado quando o fluxo de estoque tenta gerar CSV sem modelo real."""


STOCK_ALLOWED_COLUMN_HINTS = (
    'codigo',
    'cod',
    'sku',
    'id produto',
    'idproduto',
    'produto id',
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
)

STOCK_FORBIDDEN_COLUMN_HINTS = (
    'preco',
    'custo',
    'valor',
    'ncm',
    'gtin',
    'ean',
    'marca',
    'categoria',
    'imagem',
    'url',
    'peso',
    'altura',
    'largura',
    'comprimento',
    'profundidade',
    'observacao',
    'obs',
    'fornecedor',
)

MINIMUM_STOCK_REQUIRED_HINTS = ('balanco', 'saldo', 'estoque', 'quantidade', 'qtd')


def _valid_model(df_model: pd.DataFrame | None) -> bool:
    return isinstance(df_model, pd.DataFrame) and len(df_model.columns) > 0


def _is_forbidden_stock_column(column: str) -> bool:
    key = normalize_key(column)
    return any(hint in key for hint in STOCK_FORBIDDEN_COLUMN_HINTS)


def _is_allowed_stock_column(column: str) -> bool:
    key = normalize_key(column)
    if _is_forbidden_stock_column(column):
        return False
    return any(hint in key for hint in STOCK_ALLOWED_COLUMN_HINTS)


def _has_stock_quantity_column(model: pd.DataFrame) -> bool:
    for column in model.columns:
        key = normalize_key(column)
        if any(hint in key for hint in MINIMUM_STOCK_REQUIRED_HINTS):
            return True
    return False


def _protect_stock_mapping(mapping: dict[str, str], model: pd.DataFrame) -> dict[str, str]:
    """Preserva o modelo anexado e bloqueia preenchimento indevido.

    O CSV final de estoque deve manter exatamente as colunas e a ordem do
    modelo anexado na primeira etapa. Campos comerciais ou de cadastro que
    existirem nesse modelo permanecem no arquivo, mas ficam vazios para não
    contaminar a atualização de estoque.
    """
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
    if not _valid_model(df_model):
        raise MissingEstoqueModelError(
            'Modelo de estoque do Bling não carregado. Envie o modelo para gerar somente as colunas solicitadas.'
        )

    model = df_model.copy().fillna('')
    if not _has_stock_quantity_column(model):
        raise MissingEstoqueModelError(
            'Modelo de estoque inválido. Não encontrei coluna de saldo, balanço, estoque ou quantidade.'
        )

    source = df_source.copy().fillna('') if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    raw_mapping = super_auto_map_columns(source, model)
    mapping = _protect_stock_mapping(raw_mapping, model)
    final = apply_mapping(source, model, mapping)
    final = final.reindex(columns=list(model.columns), fill_value='')
    final = _fill_deposito(final, deposito)
    return sanitize_for_bling(final), mapping
