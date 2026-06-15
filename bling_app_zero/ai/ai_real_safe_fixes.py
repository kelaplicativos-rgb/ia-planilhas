from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bling_app_zero.core.gtin import clean_gtin, looks_like_gtin_column
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.core.user_rules import get_user_rules

TITLE_MAX_CHARS = 59
MAX_BLING_IMAGES = 6
DESCRIPTION_NOISE_TERMS = (
    'ainda nao ha para este produto',
    'ainda não há para este produto',
    'ainda nao ha avaliacoes para este produto',
    'ainda não há avaliações para este produto',
    'calcule o frete',
    'adicionar ao carrinho',
    'comprar',
    'continuar comprando',
    'seja o primeiro a avaliar',
)


@dataclass(frozen=True)
class SafeFixSuggestion:
    id: str
    kind: str
    title: str
    description: str
    column: str
    rows: int


def _safe_columns(df: pd.DataFrame | None) -> list[str]:
    return [str(column) for column in df.columns] if isinstance(df, pd.DataFrame) else []


def _column_key(column: object) -> str:
    return normalize_key(str(column or '')).replace(' ', '_')


def _rule_enabled(key: str, default: bool = True) -> bool:
    try:
        return bool(get_user_rules().get(key, default))
    except Exception:
        return default


def _is_title_column(column: object) -> bool:
    key = _column_key(column)
    return key in {'titulo', 'título', 'nome', 'nome_do_produto', 'produto'} or key.startswith('titulo_') or key.startswith('nome_')


def _is_description_column(column: object) -> bool:
    key = _column_key(column)
    return any(term in key for term in ['descricao', 'descrição', 'descricao_completa', 'descrição_completa', 'detalhes', 'caracteristicas', 'características'])


def _is_image_column(column: object) -> bool:
    key = _column_key(column)
    return any(term in key for term in ['imagem', 'image', 'foto', 'url_imagem', 'url_imagens', 'imagens'])


def _compact_spaces(text: object) -> str:
    return ' '.join(clean_cell(text).split())


def _smart_title(text: object, *, max_chars: int = TITLE_MAX_CHARS) -> str:
    value = _compact_spaces(text)
    if len(value) <= max_chars:
        return value
    cut = value[:max_chars].rstrip()
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0].rstrip()
    return cut or value[:max_chars].rstrip()


def _clean_description_noise(text: object) -> str:
    value = _compact_spaces(text)
    if not value:
        return ''
    lower_value = value.lower()
    positions = [lower_value.find(term.lower()) for term in DESCRIPTION_NOISE_TERMS if lower_value.find(term.lower()) >= 0]
    if positions:
        return value[: min(positions)].strip(' -|,.;')
    normalized = normalize_key(value)
    normalized_positions = [normalized.find(normalize_key(term)) for term in DESCRIPTION_NOISE_TERMS if normalized.find(normalize_key(term)) >= 0]
    if not normalized_positions:
        return value
    ratio = min(normalized_positions) / max(len(normalized), 1)
    approx = int(len(value) * ratio)
    return value[:approx].strip(' -|,.;') or value


def _image_parts(text: object) -> list[str]:
    value = _compact_spaces(text)
    if not value:
        return []
    normalized = value.replace(';', '|').replace(',', '|')
    raw_parts = [part.strip().strip('"\'[]()') for part in normalized.split('|')]
    parts: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        if not part or not part.lower().startswith(('http://', 'https://')) or part in seen:
            continue
        seen.add(part)
        parts.append(part)
    return parts


def _fix_image_separator(text: object) -> str:
    value = _compact_spaces(text)
    if not value or '|' in value or ',' not in value:
        return value
    if 'http://' not in value and 'https://' not in value:
        return value
    parts = [part.strip() for part in value.split(',') if part.strip()]
    if len(parts) <= 1:
        return value
    if not all(('http://' in part or 'https://' in part) for part in parts):
        return value
    return '|'.join(parts)


def _limit_images_to_bling(text: object, *, max_images: int = MAX_BLING_IMAGES) -> str:
    parts = _image_parts(text)
    if not parts:
        return _compact_spaces(text)
    return '|'.join(parts[:max_images])


def _needs_bling_image_limit(text: object, *, max_images: int = MAX_BLING_IMAGES) -> bool:
    return len(_image_parts(text)) > max_images


def build_safe_fix_suggestions(df_final_universal: pd.DataFrame | None) -> list[SafeFixSuggestion]:
    if not isinstance(df_final_universal, pd.DataFrame) or df_final_universal.empty:
        return []

    suggestions: list[SafeFixSuggestion] = []
    limit_images_enabled = _rule_enabled('limit_bling_images', True)

    for column in _safe_columns(df_final_universal):
        if column not in df_final_universal.columns:
            continue
        series = df_final_universal[column].fillna('').astype(str)

        if looks_like_gtin_column(column):
            rows = 0
            for value in series.tolist():
                raw = _compact_spaces(value)
                if raw and clean_gtin(raw) != raw:
                    rows += 1
            if rows:
                suggestions.append(SafeFixSuggestion('fix_gtin_invalid', 'gtin', 'Limpar GTIN/EAN inválido', f'Limpa valores inválidos na coluna "{column}", deixando vazio quando não for um GTIN/EAN seguro.', column, rows))

        if _is_image_column(column):
            rows = sum(1 for value in series.tolist() if _fix_image_separator(value) != _compact_spaces(value))
            if rows:
                suggestions.append(SafeFixSuggestion('fix_image_separator', 'image', 'Corrigir separador de imagens', f'Troca vírgula por | em URLs de imagem na coluna "{column}".', column, rows))

            limit_rows = sum(1 for value in series.tolist() if _needs_bling_image_limit(value)) if limit_images_enabled else 0
            if limit_rows:
                suggestions.append(SafeFixSuggestion('fix_bling_image_limit', 'image_limit', 'Limitar imagens para Bling', f'Mantém no máximo {MAX_BLING_IMAGES} imagens por produto na coluna "{column}" para evitar rejeição no Bling.', column, limit_rows))

        if _is_title_column(column):
            rows = sum(1 for value in series.tolist() if len(_compact_spaces(value)) > TITLE_MAX_CHARS)
            if rows:
                suggestions.append(SafeFixSuggestion('fix_title_length', 'title', 'Ajustar títulos até 59 caracteres', f'Encurta títulos longos na coluna "{column}" sem cortar palavra no meio.', column, rows))

        if _is_description_column(column):
            rows = sum(1 for value in series.tolist() if _clean_description_noise(value) != _compact_spaces(value))
            if rows:
                suggestions.append(SafeFixSuggestion('fix_description_noise', 'description', 'Limpar ruído em descrições', f'Remove trechos de avaliação, frete e compra da coluna "{column}".', column, rows))
    return suggestions


def apply_safe_fixes(df_final_universal: pd.DataFrame | None, selected_ids: list[str] | None = None) -> tuple[pd.DataFrame, list[SafeFixSuggestion]]:
    if not isinstance(df_final_universal, pd.DataFrame) or df_final_universal.empty:
        return pd.DataFrame(), []

    selected = set(selected_ids or [])
    all_suggestions = build_safe_fix_suggestions(df_final_universal)
    suggestions = [item for item in all_suggestions if not selected or item.id in selected]
    if not suggestions:
        return df_final_universal.copy().fillna(''), []

    out = df_final_universal.copy().fillna('')
    active_ids = {item.id for item in suggestions}

    for column in _safe_columns(out):
        if column not in out.columns:
            continue
        if 'fix_gtin_invalid' in active_ids and looks_like_gtin_column(column):
            out[column] = out[column].map(lambda value: clean_gtin(value) if _compact_spaces(value) else '')
        if 'fix_image_separator' in active_ids and _is_image_column(column):
            out[column] = out[column].map(_fix_image_separator)
        if 'fix_bling_image_limit' in active_ids and _is_image_column(column):
            out[column] = out[column].map(_limit_images_to_bling)
        if 'fix_title_length' in active_ids and _is_title_column(column):
            out[column] = out[column].map(_smart_title)
        if 'fix_description_noise' in active_ids and _is_description_column(column):
            out[column] = out[column].map(_clean_description_noise)

    return out.fillna(''), suggestions


__all__ = ['SafeFixSuggestion', 'apply_safe_fixes', 'build_safe_fix_suggestions']
