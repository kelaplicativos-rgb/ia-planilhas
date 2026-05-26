from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from bling_app_zero.core.text import normalize_key

MODEL_CONTRACT_TYPE_KEY = 'destination_model_contract_type'
MODEL_CONTRACT_LABEL_KEY = 'destination_model_contract_label'
MODEL_CONTRACT_CONFIDENCE_KEY = 'destination_model_contract_confidence'
MODEL_CONTRACT_REASON_KEY = 'destination_model_contract_reason'

CADASTRO_SIGNALS = (
    'descricao', 'descrição', 'nome', 'produto', 'codigo', 'código', 'sku', 'gtin', 'ean',
    'ncm', 'marca', 'categoria', 'imagem', 'imagens', 'url_imagens', 'descricao_complementar',
    'descrição_complementar', 'caracteristicas', 'características', 'ficha_tecnica', 'ficha_técnica',
    'peso', 'altura', 'largura', 'comprimento', 'profundidade',
)
STOCK_SIGNALS = (
    'deposito', 'depósito', 'balanco', 'balanço', 'saldo', 'estoque', 'quantidade', 'qtd',
)
PRICE_UPDATE_SIGNALS = (
    'preco', 'preço', 'preco_unitario', 'preço_unitário', 'preco unitario', 'preço unitário',
    'valor', 'valor_unitario', 'valor unitario', 'custo', 'preco_custo', 'preço custo',
)
PRICE_UPDATE_REQUIRED = (
    'preco', 'preço', 'preco_unitario', 'preço_unitário', 'preco unitario', 'preço unitário', 'valor',
)
ID_SIGNALS = (
    'id', 'id_produto', 'id produto', 'codigo', 'código', 'sku', 'gtin', 'ean',
)
BLING_REQUIRED_HINTS = (
    'obrigatorio', 'obrigatório',
)

CONTRACT_LABELS = {
    'cadastro': 'Bling Cadastro',
    'estoque': 'Bling Estoque',
    'atualizacao_preco': 'Bling Atualização de Preços',
    'universal': 'Modelo Universal',
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


def _has_any(key: str, signals: tuple[str, ...]) -> bool:
    normalized_signals = [normalize_key(signal).replace(' ', '_') for signal in signals]
    return any(signal and signal in key for signal in normalized_signals)


def _score(keys: list[str], signals: tuple[str, ...]) -> int:
    return sum(1 for key in keys if _has_any(key, signals))


def detect_model_contract(df: pd.DataFrame | None) -> ModelContractDetection:
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        return ModelContractDetection('universal', CONTRACT_LABELS['universal'], 0.0, 'modelo_ausente_ou_sem_colunas', {}, [])

    columns = [str(column) for column in df.columns]
    keys = _column_keys(columns)
    stock_score = _score(keys, STOCK_SIGNALS)
    price_score = _score(keys, PRICE_UPDATE_SIGNALS)
    cadastro_score = _score(keys, CADASTRO_SIGNALS)
    id_score = _score(keys, ID_SIGNALS)
    required_score = _score(keys, BLING_REQUIRED_HINTS)
    has_stock_quantity = any(_has_any(key, ('balanco', 'balanço', 'saldo', 'estoque', 'quantidade', 'qtd')) for key in keys)
    has_deposit = any(_has_any(key, ('deposito', 'depósito')) for key in keys)
    has_price_required = any(_has_any(key, PRICE_UPDATE_REQUIRED) for key in keys)
    has_cadastro_only = any(_has_any(key, ('ncm', 'marca', 'categoria', 'imagem', 'imagens', 'url_imagens', 'descricao_complementar', 'ficha_tecnica', 'caracteristicas')) for key in keys)

    scores = {
        'cadastro': cadastro_score,
        'estoque': stock_score,
        'atualizacao_preco': price_score,
        'id': id_score,
        'obrigatorio': required_score,
    }

    if has_stock_quantity and (has_deposit or stock_score >= 2) and not has_cadastro_only:
        return ModelContractDetection(
            'estoque', CONTRACT_LABELS['estoque'], 0.96,
            'colunas_deposito_saldo_balanco_estoque_detectadas_sem_campos_exclusivos_de_cadastro', scores, columns,
        )

    if has_price_required and id_score >= 1 and not has_stock_quantity and not has_cadastro_only:
        return ModelContractDetection(
            'atualizacao_preco', CONTRACT_LABELS['atualizacao_preco'], 0.90,
            'colunas_de_identificacao_e_preco_detectadas_sem_saldo_estoque_e_sem_campos_exclusivos_de_cadastro', scores, columns,
        )

    if has_cadastro_only or cadastro_score >= max(4, stock_score + price_score):
        return ModelContractDetection(
            'cadastro', CONTRACT_LABELS['cadastro'], 0.88,
            'campos_de_cadastro_produto_detectados', scores, columns,
        )

    if stock_score > cadastro_score and stock_score >= 2:
        return ModelContractDetection('estoque', CONTRACT_LABELS['estoque'], 0.78, 'predominio_de_campos_de_estoque', scores, columns)

    if price_score >= 2 and id_score >= 1:
        return ModelContractDetection('atualizacao_preco', CONTRACT_LABELS['atualizacao_preco'], 0.76, 'predominio_de_campos_de_preco', scores, columns)

    return ModelContractDetection('universal', CONTRACT_LABELS['universal'], 0.60, 'contrato_generico_sem_assinatura_bling_suficiente', scores, columns)


def normalize_contract_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('-', '_').replace(' ', '_')
    if text in {'estoque', 'bling_estoque', 'stock'}:
        return 'estoque'
    if text in {'cadastro', 'bling_cadastro', 'produtos', 'produto'}:
        return 'cadastro'
    if text in {'atualizacao_preco', 'atualizacao_precos', 'atualização_preço', 'atualização_preços', 'preco', 'precos', 'preço', 'preços'}:
        return 'atualizacao_preco'
    if text in {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}:
        return 'universal'
    return ''


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
