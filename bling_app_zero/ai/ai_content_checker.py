from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.ai.ai_dataframe_tools import detect_value_kind, normalize_column_name, sample_column_values
from bling_app_zero.ai.ai_schema import AIResult

EXPECTED_KIND_BY_NAME = {
    'preco': 'preco',
    'valor': 'preco',
    'ean': 'gtin',
    'gtin': 'gtin',
    'codigo de barras': 'gtin',
    'barcode': 'gtin',
    'imagem': 'url',
    'foto': 'url',
    'url': 'url',
    'estoque': 'inteiro',
    'quantidade': 'inteiro',
    'qtd': 'inteiro',
    'saldo': 'inteiro',
    'descricao': 'texto_curto',
    'produto': 'texto_curto',
    'nome': 'texto_curto',
}


def _expected_kind(column: str) -> str:
    normalized = normalize_column_name(column)
    for token, kind in EXPECTED_KIND_BY_NAME.items():
        if token in normalized:
            return kind
    return ''


def check_content_coherence(df: pd.DataFrame) -> AIResult:
    issues: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    if not isinstance(df, pd.DataFrame) or df.empty:
        return AIResult(ok=True, task='content_checker', message='Sem dados para checar.', data={'issues': [], 'profiles': []})

    for column in df.columns:
        samples = sample_column_values(df, str(column))
        detected = detect_value_kind(samples)
        expected = _expected_kind(str(column))
        profiles.append({'column': str(column), 'expected_kind': expected, 'detected_kind': detected, 'sample_values': samples})
        if not expected or detected == 'vazio':
            continue
        mismatch = False
        if expected == 'preco' and detected not in {'preco', 'inteiro'}:
            mismatch = True
        elif expected == 'gtin' and detected != 'gtin':
            mismatch = True
        elif expected == 'url' and detected != 'url':
            mismatch = True
        elif expected == 'inteiro' and detected not in {'inteiro', 'preco'}:
            mismatch = True
        if mismatch:
            issues.append(
                {
                    'severity': 'atenção',
                    'column': str(column),
                    'message': f'Cabeçalho parece {expected}, mas o conteúdo parece {detected}.',
                    'sample_values': samples[:5],
                }
            )

    return AIResult(
        ok=True,
        task='content_checker',
        message=f'{len(issues)} possível(is) incoerência(s) encontrada(s).',
        data={'issues': issues, 'profiles': profiles},
    )


__all__ = ['check_content_coherence']
