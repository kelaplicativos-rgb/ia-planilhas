from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bling_app_zero.core.text import clean_cell, normalize_key

TITLE_MAX_CHARS = 59
DESCRIPTION_MIN_CHARS = 180


@dataclass(frozen=True)
class EnrichmentSuggestion:
    id: str
    kind: str
    title: str
    description: str
    column: str
    rows: int


def _columns(df: pd.DataFrame | None) -> list[str]:
    return [str(column) for column in df.columns] if isinstance(df, pd.DataFrame) else []


def _key(value: object) -> str:
    return normalize_key(str(value or '')).replace(' ', '_')


def _compact(value: object) -> str:
    return ' '.join(clean_cell(value).split())


def _is_title_col(column: object) -> bool:
    key = _key(column)
    return key in {'titulo', 'título', 'nome', 'nome_do_produto', 'produto'} or key.startswith('titulo_') or key.startswith('nome_')


def _is_description_col(column: object) -> bool:
    key = _key(column)
    return any(term in key for term in ['descricao', 'descrição', 'descricao_completa', 'descrição_completa', 'detalhes', 'caracteristicas', 'características'])


def _is_brand_col(column: object) -> bool:
    return any(term in _key(column) for term in ['marca', 'brand', 'fabricante'])


def _is_model_col(column: object) -> bool:
    return any(term in _key(column) for term in ['modelo', 'model', 'referencia', 'referência'])


def _is_category_col(column: object) -> bool:
    return any(term in _key(column) for term in ['categoria', 'category', 'departamento'])


def _best_col(df: pd.DataFrame, predicate) -> str:
    for column in _columns(df):
        if predicate(column):
            return column
    return ''


def _title_case_pt(text: object) -> str:
    value = _compact(text)
    if not value:
        return ''
    upper_tokens = {'usb', 'hdmi', 'rgb', 'led', 'wifi', 'wi-fi', 'bt', 'sd', 'tf', 'pc', 'tv', 'lcd', 'ips'}
    small_tokens = {'de', 'da', 'do', 'das', 'dos', 'para', 'com', 'sem', 'e'}
    words: list[str] = []
    for index, word in enumerate(value.split()):
        raw = word.strip()
        low = raw.lower()
        if low in upper_tokens:
            words.append(low.upper())
        elif index > 0 and low in small_tokens:
            words.append(low)
        elif any(char.isdigit() for char in raw):
            words.append(raw.upper() if len(raw) <= 8 else raw)
        else:
            words.append(low.capitalize())
    return ' '.join(words)


def _fit_title(text: object, max_chars: int = TITLE_MAX_CHARS) -> str:
    value = _title_case_pt(text)
    if len(value) <= max_chars:
        return value
    cut = value[:max_chars].rstrip()
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0].rstrip()
    return cut or value[:max_chars].rstrip()


def _compose_description(row: pd.Series, title_col: str, desc_col: str, brand_col: str, model_col: str, category_col: str) -> str:
    current = _compact(row.get(desc_col, '')) if desc_col else ''
    title = _compact(row.get(title_col, '')) if title_col else ''
    brand = _compact(row.get(brand_col, '')) if brand_col else ''
    model = _compact(row.get(model_col, '')) if model_col else ''
    category = _compact(row.get(category_col, '')) if category_col else ''

    base = current or title
    if not base:
        return current

    parts: list[str] = []
    headline = title or base
    parts.append(f'{headline}.')

    details: list[str] = []
    if brand and brand.lower() not in headline.lower():
        details.append(f'marca {brand}')
    if model and model.lower() not in headline.lower():
        details.append(f'modelo {model}')
    if category:
        details.append(f'categoria {category}')
    if details:
        parts.append('Produto com ' + ', '.join(details) + '.')

    if current and current.lower() not in ' '.join(parts).lower():
        parts.append(current)

    text = ' '.join(parts)
    return text[:2000].strip()


def build_enrichment_suggestions(df_final_universal: pd.DataFrame | None) -> list[EnrichmentSuggestion]:
    if not isinstance(df_final_universal, pd.DataFrame) or df_final_universal.empty:
        return []

    suggestions: list[EnrichmentSuggestion] = []
    for column in _columns(df_final_universal):
        series = df_final_universal[column].fillna('').astype(str)
        if _is_title_col(column):
            rows = sum(1 for value in series.tolist() if _compact(value) and _fit_title(value) != _compact(value))
            if rows:
                suggestions.append(EnrichmentSuggestion('enrich_title_grammar_59', 'title', 'Melhorar títulos até 59 caracteres', 'Corrige caixa/ortografia simples e ajusta título para até 59 caracteres sem inventar dados.', column, rows))
        if _is_description_col(column):
            rows = sum(1 for value in series.tolist() if _compact(value) and len(_compact(value)) < DESCRIPTION_MIN_CHARS)
            if rows:
                suggestions.append(EnrichmentSuggestion('enrich_description_large', 'description', 'Ampliar descrições curtas', 'Monta descrição maior usando apenas dados existentes no produto, como nome, marca, modelo e categoria.', column, rows))
    return suggestions


def apply_enrichment(df_final_universal: pd.DataFrame | None, selected_ids: list[str] | None = None) -> tuple[pd.DataFrame, list[EnrichmentSuggestion]]:
    if not isinstance(df_final_universal, pd.DataFrame) or df_final_universal.empty:
        return pd.DataFrame(), []

    selected = set(selected_ids or [])
    suggestions = [item for item in build_enrichment_suggestions(df_final_universal) if not selected or item.id in selected]
    if not suggestions:
        return df_final_universal.copy().fillna(''), []

    out = df_final_universal.copy().fillna('')
    active_ids = {item.id for item in suggestions}
    title_col = _best_col(out, _is_title_col)
    desc_col = _best_col(out, _is_description_col)
    brand_col = _best_col(out, _is_brand_col)
    model_col = _best_col(out, _is_model_col)
    category_col = _best_col(out, _is_category_col)

    if 'enrich_title_grammar_59' in active_ids:
        for column in _columns(out):
            if _is_title_col(column):
                out[column] = out[column].map(_fit_title)

    if 'enrich_description_large' in active_ids and desc_col:
        out[desc_col] = out.apply(lambda row: _compose_description(row, title_col, desc_col, brand_col, model_col, category_col), axis=1)

    return out.fillna(''), suggestions


__all__ = ['EnrichmentSuggestion', 'apply_enrichment', 'build_enrichment_suggestions']