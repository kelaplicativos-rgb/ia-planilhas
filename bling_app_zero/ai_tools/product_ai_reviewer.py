from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx
import pandas as pd
import streamlit as st

from bling_app_zero.core.text import clean_cell, normalize_key

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MODEL = 'gpt-4o-mini'
MAX_ROWS_PER_RUN = 60


@dataclass(frozen=True)
class ProductAISuggestion:
    row_index: int
    product_ref: str
    field: str
    column: str
    original: str
    suggested: str
    reason: str


def _unique_names(*names: str) -> list[str]:
    result: list[str] = []
    for name in names:
        for candidate in [name, str(name).upper(), str(name).lower()]:
            if candidate and candidate not in result:
                result.append(candidate)
    return result


def _secret_value(*names: str) -> str:
    expanded_names = _unique_names(*names)

    for name in expanded_names:
        value = os.getenv(name)
        if value:
            return str(value).strip()

    try:
        for name in expanded_names:
            if name in st.secrets:
                value = st.secrets.get(name)
                if value:
                    return str(value).strip()
    except Exception:
        pass

    try:
        openai_section = st.secrets.get('openai', {})
        if isinstance(openai_section, dict):
            for name in expanded_names:
                if name in openai_section and openai_section.get(name):
                    return str(openai_section.get(name) or '').strip()
            wants_key = any('key' in normalize_key(name) or 'token' in normalize_key(name) for name in expanded_names)
            wants_model = any('model' in normalize_key(name) for name in expanded_names)
            if wants_key:
                for alias in ['api_key', 'key', 'token', 'OPENAI_API_KEY', 'openai_api_key']:
                    if alias in openai_section and openai_section.get(alias):
                        return str(openai_section.get(alias) or '').strip()
            if wants_model:
                for alias in ['model', 'OPENAI_MODEL', 'openai_model']:
                    if alias in openai_section and openai_section.get(alias):
                        return str(openai_section.get(alias) or '').strip()
    except Exception:
        pass

    return ''


def ai_ready() -> bool:
    return bool(_secret_value('OPENAI_API_KEY', 'openai_api_key', 'api_key', 'key'))


def _model_name() -> str:
    return _secret_value('OPENAI_MODEL', 'openai_model', 'model') or DEFAULT_MODEL


def _safe_json_loads(text: str) -> dict[str, Any]:
    raw = str(text or '').strip()
    if raw.startswith('```'):
        raw = raw.strip('`')
        raw = raw.replace('json\n', '', 1).replace('JSON\n', '', 1)
    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _find_first_column(df: pd.DataFrame, candidates: list[str]) -> str:
    normalized_columns = {normalize_key(str(column)): str(column) for column in df.columns}
    for candidate in candidates:
        key = normalize_key(candidate)
        if key in normalized_columns:
            return normalized_columns[key]
    for column in df.columns:
        key = normalize_key(str(column))
        if any(normalize_key(candidate) in key for candidate in candidates):
            return str(column)
    return ''


def detect_product_columns(df: pd.DataFrame) -> dict[str, str]:
    return {
        'title': _find_first_column(
            df,
            [
                'Descrição',
                'Descricao',
                'Descrição do produto',
                'Nome',
                'Nome do produto',
                'Produto',
                'Título',
                'Titulo',
            ],
        ),
        'description': _find_first_column(
            df,
            [
                'Descrição complementar',
                'Descricao complementar',
                'Descrição completa',
                'Descricao completa',
                'Complementar',
                'Descrição longa',
                'Descricao longa',
            ],
        ),
        'ncm': _find_first_column(df, ['NCM', 'Classificação fiscal', 'Classificacao fiscal']),
        'sku': _find_first_column(df, ['Código', 'Codigo', 'SKU', 'Referência', 'Referencia']),
        'brand': _find_first_column(df, ['Marca', 'Fabricante']),
        'category': _find_first_column(df, ['Categoria', 'Departamento']),
    }


def _value(row: pd.Series, column: str) -> str:
    if not column or column not in row.index:
        return ''
    return clean_cell(row.get(column, ''))


def _product_ref(row: pd.Series, columns: dict[str, str]) -> str:
    for key in ['sku', 'title']:
        value = _value(row, columns.get(key, ''))
        if value:
            return value[:80]
    return f'linha {row.name}'


def _rows_payload(df: pd.DataFrame, columns: dict[str, str], max_rows: int) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for index, row in df.head(max_rows).iterrows():
        title = _value(row, columns.get('title', ''))
        description = _value(row, columns.get('description', ''))
        ncm = _value(row, columns.get('ncm', ''))
        needs_title = bool(columns.get('title')) and not title
        needs_description = bool(columns.get('description')) and (not description or len(description) < 35)
        needs_ncm = bool(columns.get('ncm')) and not ncm
        if not (needs_title or needs_description or needs_ncm):
            continue
        payload.append(
            {
                'row_index': int(index),
                'sku': _value(row, columns.get('sku', '')),
                'brand': _value(row, columns.get('brand', '')),
                'category': _value(row, columns.get('category', '')),
                'title': title,
                'description': description,
                'ncm': ncm,
                'needs': {
                    'title': needs_title,
                    'description': needs_description,
                    'ncm': needs_ncm,
                },
            }
        )
    return payload


def _normalize_suggestions(raw: list[dict[str, Any]], df: pd.DataFrame, columns: dict[str, str]) -> list[ProductAISuggestion]:
    suggestions: list[ProductAISuggestion] = []
    allowed_fields = {
        'title': columns.get('title', ''),
        'description': columns.get('description', ''),
        'ncm': columns.get('ncm', ''),
    }
    for item in raw:
        try:
            row_index = int(item.get('row_index'))
        except Exception:
            continue
        if row_index not in df.index:
            continue
        field = str(item.get('field') or '').strip().lower()
        column = allowed_fields.get(field, '')
        if not column:
            continue
        suggested = clean_cell(item.get('suggested', ''))
        if not suggested:
            continue
        if field == 'ncm':
            ncm_digits = ''.join(ch for ch in suggested if ch.isdigit())[:8]
            suggested = ncm_digits
            if len(suggested) != 8:
                continue
        original = _value(df.loc[row_index], column)
        if original.strip() == suggested.strip():
            continue
        suggestions.append(
            ProductAISuggestion(
                row_index=row_index,
                product_ref=_product_ref(df.loc[row_index], columns),
                field=field,
                column=column,
                original=original,
                suggested=suggested,
                reason=clean_cell(item.get('reason', 'Sugestão gerada pela IA.')),
            )
        )
    return suggestions


def _call_openai_for_suggestions(df: pd.DataFrame, columns: dict[str, str], actions: dict[str, bool], max_rows: int) -> list[ProductAISuggestion]:
    api_key = _secret_value('OPENAI_API_KEY', 'openai_api_key', 'api_key', 'key')
    if not api_key:
        return []

    rows = _rows_payload(df, columns, max_rows=max_rows)
    if not rows:
        return []

    enabled_actions = [name for name, enabled in actions.items() if enabled]
    system = (
        'Você é uma IA de revisão de catálogo para importação no Bling. '
        'Você melhora dados de produtos sem inventar especificações técnicas. '
        'Use somente título, descrição, marca, categoria e SKU fornecidos. '
        'Para NCM, gere apenas sugestão de 8 dígitos quando houver contexto suficiente; se não houver segurança, não sugira. '
        'Não altere preço, GTIN, estoque, depósito, código/SKU, marca ou categoria.'
    )
    user = {
        'enabled_actions': enabled_actions,
        'rules': [
            'title: reformular ou criar título curto, claro e comercial, sem inventar voltagem, cor, tamanho ou compatibilidade.',
            'description: melhorar descrição complementar com texto limpo, profissional e fiel ao conteúdo existente.',
            'ncm: sugerir NCM de 8 dígitos somente quando estiver vazio e houver contexto mínimo; caso contrário não retorne sugestão.',
            'Retorne apenas JSON.',
        ],
        'rows': rows,
        'output_schema': {
            'suggestions': [
                {
                    'row_index': 0,
                    'field': 'title | description | ncm',
                    'suggested': 'texto sugerido ou NCM de 8 dígitos',
                    'reason': 'motivo curto',
                }
            ]
        },
    }
    payload = {
        'model': _model_name(),
        'temperature': 0.2,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)},
        ],
    }

    response = httpx.post(
        OPENAI_CHAT_URL,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    content = data['choices'][0]['message']['content']
    parsed = _safe_json_loads(content)
    raw = parsed.get('suggestions', [])
    if not isinstance(raw, list):
        return []
    return _normalize_suggestions(raw, df, columns)


def _fallback_suggestions(df: pd.DataFrame, columns: dict[str, str], actions: dict[str, bool], max_rows: int) -> list[ProductAISuggestion]:
    suggestions: list[ProductAISuggestion] = []
    for index, row in df.head(max_rows).iterrows():
        title_col = columns.get('title', '')
        desc_col = columns.get('description', '')
        title = _value(row, title_col)
        description = _value(row, desc_col)
        brand = _value(row, columns.get('brand', ''))
        category = _value(row, columns.get('category', ''))
        sku = _value(row, columns.get('sku', ''))
        ref = _product_ref(row, columns)

        if actions.get('title') and title_col and not title:
            parts = [part for part in [brand, category, sku] if part]
            suggested = ' '.join(parts).strip() or 'Produto sem título definido'
            suggestions.append(ProductAISuggestion(int(index), ref, 'title', title_col, title, suggested[:120], 'Título criado por regra local porque estava vazio.'))

        if actions.get('description') and desc_col and description and len(description) < 35:
            suggested = description
            if brand and brand.lower() not in suggested.lower():
                suggested = f'{suggested} Marca: {brand}.'
            suggestions.append(ProductAISuggestion(int(index), ref, 'description', desc_col, description, suggested, 'Descrição curta preparada para revisão.'))
    return suggestions


def generate_product_ai_suggestions(
    df: pd.DataFrame,
    *,
    actions: dict[str, bool] | None = None,
    max_rows: int = MAX_ROWS_PER_RUN,
) -> tuple[list[ProductAISuggestion], str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [], 'Sem dados finais para revisar.'
    selected_actions = actions or {'title': True, 'description': True, 'ncm': True}
    columns = detect_product_columns(df)
    if not any(columns.get(key) for key in ['title', 'description', 'ncm']):
        return [], 'Não encontrei colunas de título, descrição complementar ou NCM no CSV final.'

    try:
        suggestions = _call_openai_for_suggestions(df, columns, selected_actions, max_rows=max_rows)
        if suggestions:
            return suggestions, 'Sugestões geradas pela IA conectada.'
        if ai_ready():
            return [], 'A IA conectou, mas não encontrou alterações seguras para sugerir.'
    except Exception as exc:
        local = _fallback_suggestions(df, columns, selected_actions, max_rows=max_rows)
        if local:
            return local, f'IA online falhou ({exc}). Mostrei sugestões locais seguras.'
        return [], f'IA online falhou: {exc}'

    local = _fallback_suggestions(df, columns, selected_actions, max_rows=max_rows)
    if local:
        return local, 'OPENAI_API_KEY não configurada. Mostrei sugestões locais seguras.'
    return [], 'OPENAI_API_KEY não configurada e não encontrei sugestões locais seguras.'


def suggestions_to_dataframe(suggestions: list[ProductAISuggestion]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                'Aplicar': True,
                'Linha': item.row_index,
                'Produto': item.product_ref,
                'Campo': item.field,
                'Coluna': item.column,
                'Original': item.original,
                'Sugestão IA': item.suggested,
                'Motivo': item.reason,
            }
            for item in suggestions
        ]
    )


def apply_product_ai_suggestions(df: pd.DataFrame, edited_suggestions: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if not isinstance(edited_suggestions, pd.DataFrame) or edited_suggestions.empty:
        return out
    for _, row in edited_suggestions.iterrows():
        apply = bool(row.get('Aplicar', False))
        if not apply:
            continue
        try:
            row_index = int(row.get('Linha'))
        except Exception:
            continue
        column = str(row.get('Coluna') or '').strip()
        suggested = clean_cell(row.get('Sugestão IA', ''))
        if row_index not in out.index or column not in out.columns or not suggested:
            continue
        out.at[row_index, column] = suggested
    return out


__all__ = [
    'ProductAISuggestion',
    'ai_ready',
    'apply_product_ai_suggestions',
    'detect_product_columns',
    'generate_product_ai_suggestions',
    'suggestions_to_dataframe',
]
