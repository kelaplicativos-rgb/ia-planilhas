from __future__ import annotations

from bling_app_zero.core.column_contract import RequestedField
from bling_app_zero.engines.fast_site_scraper.constants import DESCRIPTION_TRIGGER_KINDS
from bling_app_zero.engines.fast_site_scraper.models import FastProductData


def default_columns(operation: str) -> list[str]:
    if operation == 'estoque':
        return ['Código', 'Descrição', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)']
    return [
        'URL', 'Código', 'SKU', 'GTIN', 'Descrição', 'Descrição complementar',
        'Características', 'Ficha técnica', 'Nome', 'Preço', 'Preço unitário (OBRIGATÓRIO)',
        'URL Imagens', 'Imagens', 'Marca', 'Categoria', 'Estoque',
    ]


def needed_kinds(contract: list[RequestedField], operation: str = 'cadastro') -> set[str]:
    kinds = {field.kind for field in contract}
    if 'codigo' in kinds or 'id_produto' in kinds:
        kinds.add('gtin')
    if operation == 'cadastro' and kinds.intersection(DESCRIPTION_TRIGGER_KINDS):
        kinds.add('descricao_complementar')
    return kinds


def important_kinds(contract: list[RequestedField]) -> set[str]:
    kinds = {field.kind for field in contract if field.kind != 'custom'}
    if 'codigo' in kinds or 'id_produto' in kinds:
        kinds.add('gtin')
    kinds -= {'deposito', 'data', 'observacao'}
    return kinds or {'url'}


def value_for_kind(product: FastProductData, kind: str) -> str:
    if kind == 'url':
        return product.url
    if kind == 'id_produto':
        return product.id_produto or product.codigo or product.gtin
    if kind == 'codigo':
        return product.codigo or product.gtin or product.id_produto
    if kind == 'gtin':
        return product.gtin
    if kind in {'descricao', 'descricao_curta', 'nome_apoio'}:
        return product.descricao
    if kind == 'descricao_complementar':
        return product.descricao_complementar
    if kind == 'ficha_tecnica':
        return product.ficha_tecnica
    if kind == 'caracteristicas':
        return product.caracteristicas
    if kind in {'preco_unitario', 'preco_custo'}:
        return product.preco
    if kind == 'estoque':
        return product.estoque
    if kind == 'imagem':
        return product.imagem
    if kind == 'marca':
        return product.marca
    if kind == 'categoria':
        return product.categoria
    return ''


__all__ = ['default_columns', 'important_kinds', 'needed_kinds', 'value_for_kind']
