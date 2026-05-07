from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.text import normalize_key

SYNONYMS = {
    'codigo': ['codigo', 'cod', 'sku', 'referencia', 'id produto', 'ref'],
    'descricao': ['descricao', 'nome', 'produto', 'titulo', 'title'],
    'descricao curta': ['descricao curta', 'resumo', 'complementar'],
    'preco': ['preco', 'valor', 'preco venda', 'preco unitario', 'price'],
    'estoque': ['estoque', 'saldo', 'quantidade', 'qtd', 'balanco', 'stock'],
    'gtin': ['gtin', 'ean', 'codigo barras', 'codigo de barras', 'barcode'],
    'marca': ['marca', 'fabricante', 'brand'],
    'categoria': ['categoria', 'departamento', 'breadcrumb', 'category'],
    'imagem': ['imagem', 'imagens', 'foto', 'fotos', 'url imagem', 'url imagens', 'image'],
    'deposito': ['deposito', 'almoxarifado', 'local estoque'],
    'ncm': ['ncm'],
}


def _score(target: str, source: str) -> int:
    target_key = normalize_key(target)
    source_key = normalize_key(source)
    if not target_key or not source_key:
        return 0
    if target_key == source_key:
        return 100
    score = 0
    if target_key in source_key or source_key in target_key:
        score += 45
    target_tokens = set(target_key.split())
    source_tokens = set(source_key.split())
    score += len(target_tokens & source_tokens) * 15
    for family, names in SYNONYMS.items():
        fam = normalize_key(family)
        if fam in target_key:
            for synonym in names:
                if normalize_key(synonym) in source_key:
                    score += 35
    return score


def auto_map_columns(df_source: pd.DataFrame, df_model: pd.DataFrame) -> dict[str, str]:
    if df_source is None or df_model is None or df_source.empty and len(df_source.columns) == 0:
        return {}

    source_cols = [str(c) for c in df_source.columns]
    model_cols = [str(c) for c in df_model.columns]
    used: set[str] = set()
    mapping: dict[str, str] = {}

    for model_col in model_cols:
        best_col = ''
        best_score = 0
        for source_col in source_cols:
            if source_col in used:
                continue
            score = _score(model_col, source_col)
            if score > best_score:
                best_score = score
                best_col = source_col
        if best_col and best_score >= 30:
            mapping[model_col] = best_col
            used.add(best_col)
        else:
            mapping[model_col] = ''

    return mapping


def apply_mapping(df_source: pd.DataFrame, df_model: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    if df_model is None or len(df_model.columns) == 0:
        return pd.DataFrame()
    if df_source is None or df_source.empty:
        return pd.DataFrame(columns=df_model.columns)

    out = pd.DataFrame(index=df_source.index)
    for model_col in df_model.columns:
        source_col = mapping.get(str(model_col), '') if isinstance(mapping, dict) else ''
        if source_col and source_col in df_source.columns:
            out[model_col] = df_source[source_col].fillna('').astype(str)
        else:
            out[model_col] = ''
    return out.fillna('')


def build_model_from_columns(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=[str(c) for c in columns])
