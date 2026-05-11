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


def _protect_stock_mapping(mapping: dict[str, str]) -> dict[str, str]:
    """Remove restos de cadastro do fluxo de estoque.

    Atualização de estoque não deve preencher preço, custo, categoria, imagem,
    GTIN, observação ou campos comerciais, mesmo quando uma planilha/modelo
    misturado trouxer essas colunas. Esses campos ficam vazios para impedir que
    o motor antigo de cadastro interfira no CSV de estoque.
    """
    protected: dict[str, str] = {}
    for target, source in mapping.items():
        protected[str(target)] = str(source or '') if _is_allowed_stock_column(str(target)) else ''
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
    source = df_source.copy().fillna('') if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    raw_mapping = super_auto_map_columns(source, model)
    mapping = _protect_stock_mapping(raw_mapping)
    final = apply_mapping(source, model, mapping)
    final = _fill_deposito(final, deposito)
    return sanitize_for_bling(final), mapping
