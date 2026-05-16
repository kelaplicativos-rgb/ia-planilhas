from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bling_app_zero.ai.ai_dataframe_tools import normalize_column_name

MODEL_TYPE_CADASTRO = 'cadastro'
MODEL_TYPE_ESTOQUE = 'estoque'
MODEL_TYPE_PRECOS = 'precos'
MODEL_TYPE_MULTILOJAS = 'multilojas'
MODEL_TYPE_PERSONALIZADO = 'personalizado'

KEYWORDS = {
    MODEL_TYPE_CADASTRO: {
        'descricao', 'nome produto', 'produto', 'titulo', 'gtin', 'ean', 'ncm', 'categoria', 'marca', 'imagem', 'url imagem', 'descricao complementar'
    },
    MODEL_TYPE_ESTOQUE: {
        'estoque', 'saldo', 'quantidade', 'qtd', 'deposito', 'balanco', 'localizacao'
    },
    MODEL_TYPE_PRECOS: {
        'preco', 'valor', 'preco venda', 'preco promocional', 'preco custo', 'margem', 'desconto'
    },
    MODEL_TYPE_MULTILOJAS: {
        'loja', 'marketplace', 'canal', 'magalu', 'olist', 'shopee', 'mercado livre', 'amazon', 'tray', 'tiny', 'kyte'
    },
}


@dataclass(frozen=True)
class ModelDetection:
    model_type: str
    confidence: float
    reason: str
    scores: dict[str, int]
    columns: list[str]


def _columns(df_model: pd.DataFrame | None) -> list[str]:
    if not isinstance(df_model, pd.DataFrame):
        return []
    return [str(column) for column in df_model.columns]


def _score_columns(columns: list[str]) -> dict[str, int]:
    normalized = [normalize_column_name(column) for column in columns]
    joined = ' | '.join(normalized)
    scores: dict[str, int] = {}
    for model_type, keywords in KEYWORDS.items():
        score = 0
        for keyword in keywords:
            key = normalize_column_name(keyword)
            if any(key == column or key in column for column in normalized):
                score += 2
            elif key in joined:
                score += 1
        scores[model_type] = score
    return scores


def detect_model_type(df_model: pd.DataFrame | None) -> ModelDetection:
    columns = _columns(df_model)
    if not columns:
        return ModelDetection(MODEL_TYPE_PERSONALIZADO, 0.0, 'Modelo sem colunas detectáveis.', {}, [])

    scores = _score_columns(columns)
    estoque_score = scores.get(MODEL_TYPE_ESTOQUE, 0)
    cadastro_score = scores.get(MODEL_TYPE_CADASTRO, 0)
    precos_score = scores.get(MODEL_TYPE_PRECOS, 0)
    multilojas_score = scores.get(MODEL_TYPE_MULTILOJAS, 0)

    if multilojas_score >= 2 and precos_score >= 2:
        detected = MODEL_TYPE_MULTILOJAS
    else:
        detected = max(scores, key=lambda key: scores.get(key, 0)) if scores else MODEL_TYPE_PERSONALIZADO

    best = scores.get(detected, 0)
    total = max(1, sum(max(0, value) for value in scores.values()))
    confidence = min(0.98, round(best / total, 3)) if best else 0.25

    if best <= 1:
        detected = MODEL_TYPE_PERSONALIZADO
        confidence = 0.35
        reason = 'Modelo personalizado: poucas colunas conhecidas foram encontradas.'
    elif detected == MODEL_TYPE_MULTILOJAS:
        reason = 'Modelo parece trabalhar preço por loja/canal/marketplace.'
    elif detected == MODEL_TYPE_ESTOQUE:
        reason = 'Modelo contém campos fortes de estoque, saldo, quantidade ou depósito.'
    elif detected == MODEL_TYPE_PRECOS:
        reason = 'Modelo contém campos fortes de preço, valor, margem ou desconto.'
    elif detected == MODEL_TYPE_CADASTRO:
        reason = 'Modelo contém campos de cadastro de produto, descrição, GTIN, NCM, categoria ou imagem.'
    else:
        reason = 'Modelo personalizado detectado.'

    return ModelDetection(detected, confidence, reason, scores, columns)


__all__ = [
    'MODEL_TYPE_CADASTRO',
    'MODEL_TYPE_ESTOQUE',
    'MODEL_TYPE_MULTILOJAS',
    'MODEL_TYPE_PERSONALIZADO',
    'MODEL_TYPE_PRECOS',
    'ModelDetection',
    'detect_model_type',
]
