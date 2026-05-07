from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from bling_app_zero.core.text import normalize_key


@dataclass(frozen=True)
class RequestedField:
    original: str
    key: str
    kind: str
    required: bool = False


KIND_SYNONYMS = {
    'id_produto': ['id produto', 'id', 'identificador'],
    'codigo': ['codigo produto', 'codigo', 'cod produto', 'sku', 'referencia', 'ref'],
    'gtin': ['gtin', 'ean', 'codigo de barras', 'barcode'],
    'descricao': ['descricao produto', 'descricao', 'nome produto', 'titulo', 'nome', 'produto'],
    'deposito': ['deposito', 'almoxarifado', 'local estoque'],
    'estoque': ['balanco', 'estoque', 'quantidade', 'saldo', 'qtd'],
    'preco_custo': ['preco de custo', 'preco custo', 'valor custo', 'custo'],
    'preco_unitario': ['preco unitario', 'preco de venda', 'preco venda', 'valor unitario', 'valor venda', 'preco', 'valor'],
    'observacao': ['observacao', 'obs', 'comentario'],
    'data': ['data', 'dt'],
    'url': ['url', 'link', 'pagina'],
    'nome_apoio': ['nome apoio', 'apoio', 'nome auxiliar'],
    'imagem': ['imagem', 'imagens', 'url imagens', 'foto', 'fotos'],
    'marca': ['marca', 'fabricante'],
    'categoria': ['categoria', 'departamento'],
    'ncm': ['ncm'],
}


def _clean_column_key(column_name: str) -> str:
    key = normalize_key(column_name)
    key = key.replace(' obrigatorio', '').replace(' obrigatoria', '')
    key = key.replace('*', '').strip()
    return key


def infer_kind(column_name: str) -> str:
    """Detecta o tipo da coluna priorizando nomes mais específicos."""
    key = _clean_column_key(column_name)
    if not key:
        return 'custom'

    best_kind = 'custom'
    best_score = 0

    for kind, synonyms in KIND_SYNONYMS.items():
        for synonym in synonyms:
            syn = normalize_key(synonym)
            if not syn:
                continue

            score = 0
            if key == syn:
                score = 1000 + len(syn)
            elif syn in key:
                score = 500 + len(syn)
            elif key in syn:
                score = 300 + len(key)

            if score > best_score:
                best_score = score
                best_kind = kind

    return best_kind


def build_contract(columns: Iterable[str]) -> list[RequestedField]:
    result: list[RequestedField] = []
    for column in columns:
        original = str(column or '').strip()
        if not original:
            continue
        key = normalize_key(original)
        required = '*' in original or 'obrigatorio' in key or 'obrigatoria' in key
        result.append(RequestedField(original=original, key=key, kind=infer_kind(original), required=required))
    return result


def contract_from_model(df_model: pd.DataFrame | None) -> list[RequestedField]:
    if isinstance(df_model, pd.DataFrame) and len(df_model.columns):
        return build_contract([str(c) for c in df_model.columns])
    return []


def columns_from_contract(contract: list[RequestedField]) -> list[str]:
    return [field.original for field in contract]


def kinds_from_contract(contract: list[RequestedField]) -> set[str]:
    return {field.kind for field in contract}
