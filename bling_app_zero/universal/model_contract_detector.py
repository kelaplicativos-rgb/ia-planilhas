from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from bling_app_zero.core.text import normalize_key

MODEL_CONTRACT_TYPE_KEY = 'destination_model_contract_type'
MODEL_CONTRACT_LABEL_KEY = 'destination_model_contract_label'
MODEL_CONTRACT_CONFIDENCE_KEY = 'destination_model_contract_confidence'
MODEL_CONTRACT_REASON_KEY = 'destination_model_contract_reason'

CONTRACT_LABELS = {
    'cadastro': 'Modelo para mapear',
    'estoque': 'Modelo para mapear',
    'atualizacao_preco': 'Modelo para mapear',
    'universal': 'Modelo para mapear',
}


@dataclass(frozen=True)
class ModelContractDetection:
    contract_type: str
    label: str
    confidence: float
    reason: str
    scores: dict[str, int]
    columns: list[str]


def _column_keys(columns: Iterable[object]) -> list[str]:
    return [normalize_key(str(column or '').replace('\n', ' ').replace('\r', ' ')).replace(' ', '_') for column in columns]


def detect_model_contract(df: pd.DataFrame | None) -> ModelContractDetection:
    """Retorna sempre um contrato universal para o modelo anexado.

    A classificação do arquivo do usuário é neutra; a operação explícita do fluxo
    continua sendo respeitada em ``normalize_contract_operation``.
    """
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        return ModelContractDetection('universal', CONTRACT_LABELS['universal'], 0.0, 'modelo_ausente_ou_sem_colunas', {}, [])
    columns = [str(column) for column in df.columns]
    keys = _column_keys(columns)
    return ModelContractDetection(
        'universal',
        CONTRACT_LABELS['universal'],
        1.0,
        'modelo_universal_enviado_pelo_usuario_sem_classificacao',
        {'universal': len(keys)},
        columns,
    )


def normalize_contract_operation(value: object) -> str:
    text = normalize_key(str(value or '').replace('-', ' ').replace('_', ' '))
    if text in {'', 'universal', 'modelo', 'modelo destino', 'modelo para mapear', 'planilha', 'wizard cadastro estoque'}:
        return 'universal'
    if text in {'cadastro', 'cadastro site', 'produtos', 'produto', 'cadastrar produtos'}:
        return 'cadastro'
    if text in {'estoque', 'stock', 'atualizacao estoque', 'atualização estoque', 'atualizacao de estoque', 'atualização de estoque', 'estoque site'}:
        return 'estoque'
    if text in {'atualizacao preco', 'atualização preço', 'atualizacao de preco', 'atualização de preço', 'preco', 'preço', 'price'}:
        return 'atualizacao_preco'
    return 'universal'


__all__ = [
    'CONTRACT_LABELS',
    'MODEL_CONTRACT_CONFIDENCE_KEY',
    'MODEL_CONTRACT_LABEL_KEY',
    'MODEL_CONTRACT_REASON_KEY',
    'MODEL_CONTRACT_TYPE_KEY',
    'ModelContractDetection',
    'detect_model_contract',
    'normalize_contract_operation',
]
