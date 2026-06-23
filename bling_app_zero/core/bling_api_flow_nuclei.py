from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, normalize_operation
from bling_app_zero.core.text import normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_api_flow_nuclei.py'
PROVISIONAL_CATEGORY = 'Produtos não classificados'

API_NUCLEI_SEQUENCE = (
    'auth_bling', 'origem_universal', 'normalizacao_universal', 'escolha_operacao',
    'motor_operacao', 'contrato_api_automatico', 'validacao_obrigatoria',
    'preview_final', 'envio_api_bling', 'diagnostico_por_etapa',
)

COLUMN_TERMS = {
    'identifier': ('id produto', 'id bling', 'codigo', 'código', 'sku', 'referencia', 'referência', 'gtin', 'ean'),
    'name': ('nome', 'descricao', 'descrição', 'produto', 'titulo', 'título'),
    'price': ('preco', 'preço', 'valor', 'unitario', 'unitário', 'venda', 'promocional'),
    'quantity': ('quantidade', 'qtd', 'saldo', 'estoque', 'balanco', 'balanço'),
    'deposit': ('deposito', 'depósito', 'id deposito', 'id depósito'),
    'category': ('categoria', 'departamento'),
    'brand': ('marca', 'fabricante'),
    'images': ('imagem', 'imagens', 'foto', 'fotos', 'url imagem', 'url imagens'),
}


@dataclass(frozen=True)
class ApiOperationNuclei:
    operation: str
    label: str
    required_nuclei: tuple[str, ...]
    required_groups: tuple[str, ...]
    warning_groups: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    manual_mapping_allowed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            'operation': self.operation,
            'label': self.label,
            'required_nuclei': list(self.required_nuclei),
            'required_groups': list(self.required_groups),
            'warning_groups': list(self.warning_groups),
            'notes': list(self.notes),
            'manual_mapping_allowed': self.manual_mapping_allowed,
            'responsible_file': RESPONSIBLE_FILE,
        }


@dataclass(frozen=True)
class ApiFlowValidationResult:
    operation: str
    ok: bool
    missing_groups: tuple[str, ...] = ()
    warning_groups: tuple[str, ...] = ()
    detected_columns: dict[str, list[str]] = field(default_factory=dict)
    messages: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            'operation': self.operation,
            'ok': self.ok,
            'missing_groups': list(self.missing_groups),
            'warning_groups': list(self.warning_groups),
            'detected_columns': self.detected_columns,
            'messages': list(self.messages),
            'responsible_file': RESPONSIBLE_FILE,
        }


OPERATION_NUCLEI = {
    OP_CADASTRO: ApiOperationNuclei(
        operation=OP_CADASTRO,
        label='Cadastro de produtos via API',
        required_nuclei=('origem_universal', 'normalizacao_universal', 'marca_inteligente', 'categoria_inteligente_ou_fallback', 'preco_custo', 'imagens_limitadas', 'gtin_ean', 'contrato_produto_api', 'preview_final', 'envio_produtos_api'),
        required_groups=('name', 'price'),
        warning_groups=('category', 'identifier', 'images', 'brand'),
        notes=(f'Categoria vazia deve receber fallback {PROVISIONAL_CATEGORY}.', 'Mapeamento manual bloqueado: contrato da API é automático.'),
    ),
    OP_ESTOQUE: ApiOperationNuclei(
        operation=OP_ESTOQUE,
        label='Atualização de estoque via API',
        required_nuclei=('origem_universal', 'normalizacao_universal', 'identificador_produto', 'quantidade_estoque', 'deposito_bling', 'contrato_estoque_api', 'preview_final', 'envio_estoque_api'),
        required_groups=('identifier', 'quantity'),
        warning_groups=('deposit',),
        notes=('Não exige categoria, marca, descrição longa ou imagens.', 'Depósito do Bling é obrigatório antes do envio.'),
    ),
    OP_ATUALIZACAO_PRECO: ApiOperationNuclei(
        operation=OP_ATUALIZACAO_PRECO,
        label='Atualização de preços via API',
        required_nuclei=('origem_universal', 'normalizacao_universal', 'detector_preco', 'calculadora_preco', 'identificador_produto', 'contrato_preco_api', 'preview_final', 'envio_precos_api'),
        required_groups=('identifier', 'price'),
        notes=('Não exige categoria, marca, descrição longa ou imagens.', 'Preço final e identificador são obrigatórios.'),
    ),
}


def concrete_api_operations() -> tuple[str, ...]:
    return (OP_CADASTRO, OP_ESTOQUE, OP_ATUALIZACAO_PRECO)


def api_operation_nuclei(operation: object) -> ApiOperationNuclei:
    op = normalize_operation(operation)
    return OPERATION_NUCLEI.get(op) or OPERATION_NUCLEI[OP_CADASTRO]


def api_flow_overview(operation: object) -> dict[str, object]:
    spec = api_operation_nuclei(operation)
    return {'sequence': list(API_NUCLEI_SEQUENCE), 'operation': spec.to_dict(), 'manual_mapping_allowed': False, 'api_is_final_destination_only': True, 'same_flow_and_engines': True, 'responsible_file': RESPONSIBLE_FILE}


def _norm_columns(df: pd.DataFrame) -> dict[str, str]:
    if not isinstance(df, pd.DataFrame):
        return {}
    return {str(col): normalize_key(str(col)) for col in df.columns if str(col).strip()}


def detect_column_groups(df: pd.DataFrame, groups: Iterable[str] | None = None) -> dict[str, list[str]]:
    columns = _norm_columns(df)
    selected = tuple(groups or COLUMN_TERMS.keys())
    detected: dict[str, list[str]] = {}
    for group in selected:
        terms = tuple(normalize_key(term) for term in COLUMN_TERMS.get(group, ()))
        detected[group] = [original for original, normalized in columns.items() if any(term and term in normalized for term in terms)]
    return detected


def validate_api_dataframe(df: pd.DataFrame, operation: object) -> ApiFlowValidationResult:
    spec = api_operation_nuclei(operation)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ApiFlowValidationResult(operation=spec.operation, ok=False, missing_groups=tuple(spec.required_groups), messages=('Carregue a origem dos dados antes de validar a API.',))
    groups = set(spec.required_groups) | set(spec.warning_groups)
    detected = detect_column_groups(df, groups)
    missing = tuple(group for group in spec.required_groups if not detected.get(group))
    warnings = tuple(group for group in spec.warning_groups if not detected.get(group))
    messages: list[str] = []
    if missing:
        messages.append('Campos obrigatórios ausentes: ' + ', '.join(missing))
    if spec.operation == OP_CADASTRO and 'category' in warnings:
        messages.append(f'Categoria não detectada: aplicar inteligência ou fallback {PROVISIONAL_CATEGORY}.')
    if spec.operation == OP_ESTOQUE:
        messages.append('Depósito do Bling deve estar selecionado antes do envio.')
    return ApiFlowValidationResult(operation=spec.operation, ok=not missing, missing_groups=missing, warning_groups=warnings, detected_columns=detected, messages=tuple(messages))


__all__ = ['API_NUCLEI_SEQUENCE', 'ApiFlowValidationResult', 'ApiOperationNuclei', 'OPERATION_NUCLEI', 'PROVISIONAL_CATEGORY', 'api_flow_overview', 'api_operation_nuclei', 'concrete_api_operations', 'detect_column_groups', 'validate_api_dataframe']
