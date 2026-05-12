from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    table = str.maketrans('áàãâäéèêëíìîïóòõôöúùûüç', 'aaaaaeeeeiiiiooooouuuuc')
    text = text.translate(table)
    return ''.join(ch for ch in text if ch.isalnum())


@dataclass(frozen=True)
class MultistoreDetection:
    is_multistore: bool
    confidence: float
    required_found: tuple[str, ...]
    optional_found: tuple[str, ...]
    missing: tuple[str, ...]
    message: str


REQUIRED_PATTERNS = {
    'IdProduto': {'idproduto', 'idprodutobling'},
    'ID na Loja': {'idnaloja', 'idanuncio', 'idlojavirtual'},
}
OPTIONAL_PATTERNS = {
    'Preço': {'preco', 'precovenda', 'precofinal'},
    'Preço Promocional': {'precopromocional', 'preco promocional'},
    'Nome da Loja': {'nomedaloja', 'loja', 'lojavirtual'},
    'Link Externo': {'linkexterno', 'url', 'link'},
    'ID Fornecedor': {'idfornecedor'},
    'ID Marca': {'idmarca'},
}


def _find(columns: list[str], patterns: set[str]) -> str:
    normalized = {_norm(column): column for column in columns}
    for pattern in patterns:
        if _norm(pattern) in normalized:
            return normalized[_norm(pattern)]
    return ''


def detect_multistore_model(df: pd.DataFrame) -> MultistoreDetection:
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        return MultistoreDetection(False, 0.0, (), (), tuple(REQUIRED_PATTERNS), 'Arquivo sem colunas para reconhecer.')

    columns = [str(column) for column in df.columns]
    required_found: list[str] = []
    missing: list[str] = []
    optional_found: list[str] = []

    for label, patterns in REQUIRED_PATTERNS.items():
        found = _find(columns, patterns)
        if found:
            required_found.append(found)
        else:
            missing.append(label)

    for label, patterns in OPTIONAL_PATTERNS.items():
        found = _find(columns, patterns)
        if found:
            optional_found.append(found)

    score = (len(required_found) * 0.35) + min(len(optional_found), 4) * 0.075
    confidence = min(1.0, score)
    is_multistore = len(missing) == 0 and bool(_find(columns, OPTIONAL_PATTERNS['Preço']) or _find(columns, OPTIONAL_PATTERNS['Preço Promocional']))
    message = 'Modelo de preços multilojas reconhecido.' if is_multistore else 'Modelo ainda não parece ser de preços multilojas.'
    return MultistoreDetection(is_multistore, confidence, tuple(required_found), tuple(optional_found), tuple(missing), message)


__all__ = ['MultistoreDetection', 'detect_multistore_model']
