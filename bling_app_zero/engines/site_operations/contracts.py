from __future__ import annotations

from collections.abc import Iterable

CADASTRO_DEFAULT_COLUMNS = [
    'URL',
    'Código',
    'SKU',
    'GTIN',
    'Descrição',
    'Descrição complementar',
    'Características',
    'Ficha técnica',
    'Nome',
    'Preço',
    'Preço unitário (OBRIGATÓRIO)',
    'URL Imagens',
    'Imagens',
    'Marca',
    'Categoria',
    # A busca pode acontecer antes de o modelo final ser anexado. Mantemos
    # estoque no contrato de origem para o submotor existente capturar o saldo
    # e deixá-lo disponível no mapeamento posterior.
    'Estoque',
]
URL_COLUMN_KEYS = {'url', 'link', 'produto_url', 'url_produto', 'link_produto'}


def unique_columns(columns: Iterable[str] | None) -> list[str]:
    """Limpa e deduplica colunas mantendo a ordem original."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for column in columns or []:
        text = str(column).strip()
        if text and text not in seen:
            cleaned.append(text)
            seen.add(text)
    return cleaned


def _column_key(column: object) -> str:
    text = str(column or '').strip().lower()
    for old, new in (
        ('ã', 'a'), ('á', 'a'), ('à', 'a'), ('â', 'a'),
        ('é', 'e'), ('ê', 'e'), ('í', 'i'),
        ('ó', 'o'), ('ô', 'o'), ('õ', 'o'), ('ú', 'u'), ('ç', 'c'),
    ):
        text = text.replace(old, new)
    return '_'.join(part for part in text.replace('-', ' ').replace('/', ' ').split() if part)


def _has_url_column(columns: Iterable[str]) -> bool:
    return any(_column_key(column) in URL_COLUMN_KEYS for column in columns)


def _with_site_url_column(columns: list[str]) -> list[str]:
    if not columns or _has_url_column(columns):
        return columns
    return ['URL', *columns]


def cadastro_columns(columns: Iterable[str] | None) -> list[str]:
    cleaned = unique_columns(columns)
    return _with_site_url_column(cleaned) or CADASTRO_DEFAULT_COLUMNS.copy()


def estoque_columns(columns: Iterable[str] | None) -> list[str]:
    return _with_site_url_column(unique_columns(columns))
