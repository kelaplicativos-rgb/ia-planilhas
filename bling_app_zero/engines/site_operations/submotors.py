from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from bling_app_zero.core.column_contract import build_contract


@dataclass(frozen=True)
class SiteSubmotorPlan:
    operation: str
    columns: list[str]
    active: list[str]

    @property
    def summary(self) -> str:
        return ', '.join(self.active) if self.active else 'sem submotor ativo'


KIND_TO_SUBMOTOR = {
    'url': 'links',
    'codigo': 'identificacao',
    'id_produto': 'identificacao',
    'gtin': 'gtin',
    'descricao': 'descricao',
    'descricao_curta': 'descricao',
    'nome_apoio': 'descricao',
    'descricao_complementar': 'descricao_rica',
    'ficha_tecnica': 'descricao_rica',
    'caracteristicas': 'descricao_rica',
    'preco_unitario': 'preco',
    'preco_custo': 'preco',
    'estoque': 'estoque',
    'imagem': 'imagens',
    'marca': 'marca',
    'categoria': 'categoria',
}

OPERATION_ORDER = {
    'cadastro': ['links', 'identificacao', 'descricao', 'descricao_rica', 'preco', 'gtin', 'imagens', 'marca', 'categoria', 'estoque'],
    'estoque': ['links', 'identificacao', 'gtin', 'estoque', 'descricao'],
    # Origem única por modelo: mantém todos os submotores possíveis na ordem
    # mais segura para montar uma linha completa sem separar cadastro/estoque.
    'universal': ['links', 'identificacao', 'gtin', 'descricao', 'descricao_rica', 'preco', 'estoque', 'imagens', 'marca', 'categoria'],
}

UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}


def normalize_submotor_operation(operation: str | None) -> str:
    value = str(operation or 'universal').strip().lower()
    if value in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'estoque_site'}:
        return 'estoque'
    if value in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return 'cadastro'
    if value in UNIVERSAL_ALIASES:
        return 'universal'
    return 'universal'


def build_submotor_plan(operation: str, columns: Iterable[str] | None) -> SiteSubmotorPlan:
    normalized = normalize_submotor_operation(operation)
    column_list = [str(column).strip() for column in (columns or []) if str(column).strip()]
    contract = build_contract(column_list)
    requested = {KIND_TO_SUBMOTOR[field.kind] for field in contract if field.kind in KIND_TO_SUBMOTOR}

    # Links sempre fazem parte da captura por site.
    requested.add('links')

    order = OPERATION_ORDER[normalized]
    active = [name for name in order if name in requested]
    return SiteSubmotorPlan(operation=normalized, columns=column_list, active=active)


__all__ = ['SiteSubmotorPlan', 'build_submotor_plan', 'normalize_submotor_operation']
