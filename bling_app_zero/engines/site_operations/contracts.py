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


def cadastro_columns(columns: Iterable[str] | None) -> list[str]:
    return unique_columns(columns) or CADASTRO_DEFAULT_COLUMNS.copy()


def estoque_columns(columns: Iterable[str] | None) -> list[str]:
    return unique_columns(columns)
