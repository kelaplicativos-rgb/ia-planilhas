from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx
import pandas as pd

from bling_app_zero.ai.ai_config import get_ai_model, get_user_openai_key
from bling_app_zero.core.text import clean_cell, normalize_key

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
MAX_ROWS_PER_RUN = 60
PROTECTED_COLUMN_TERMS = [
    'preco', 'preço', 'valor', 'gtin', 'ean', 'estoque', 'quantidade', 'saldo',
    'deposito', 'depósito', 'codigo', 'código', 'sku', 'id', 'imagem', 'url',
]


@dataclass(frozen=True)
class ProductAISuggestion:
    row_index: int
    product_ref: str
    field: str
    column: str
    original: str
    suggested: str
    reason: str


def ai_ready() -> bool:
    """Usa somente a chave OpenAI digitada no sidebar do Mapeia.AI.

    Regra BYOK: não procurar OPENAI_API_KEY em ambiente, st.secrets ou fallback
    administrativo. Cada usuário informa a própria chave na sessão atual.
    """
    return bool(get_user_openai_key())


def _model_name() -> str:
    return get_ai_model()


def _safe_json_loads(text: str) -> dict[str, Any]:
    raw = str(text or '').strip()
    if raw.startswith('```'):
        raw = raw.strip('`').replace('json\n', '', 1).replace('JSON\n', '', 1)
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
        'title': _find_first_column(df, ['Descrição', 'Descricao', 'Descrição do produto', 'Nome', 'Nome do produto', 'Produto', 'Título', 'Titulo']),
        'description': _find_first_column(df, ['Descrição complementar', 'Descricao complementar', 'Descrição completa', 'Descricao completa', 'Complementar', 'Descrição longa', 'Descricao longa']),
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


def _is_protected_column(column: str) -> bool:
    key = normalize_key(str(column or ''))
    return not key or any(normalize_key(term) in key for term in PROTECTED_COLUMN_TERMS)


def _safe_row_data(row: pd.Series, max_columns: int = 36) -> dict[str, str]:
    data: dict[str, str] = {}
    for column in list(row.index)[:max_columns]:
        data[str(column)] = clean_cell(row.get(column, ''))[:900]
    return data


def _rows_payload(
    df: pd.DataFrame,
    columns: dict[str, str],
    max_rows: int,
    include_custom_task_rows: bool = False,
    include_grammar_rows: bool = False,
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for index, row in df.head(max_rows).iterrows():
        title = _value(row, columns.get('title', ''))
        description = _value(row, columns.get('description', ''))
        ncm = _value(row, columns.get('ncm', ''))
        needs_title = bool(columns.get('title')) and not title
        needs_description = bool(columns.get('description')) and (not description or len(description) < 35)
        needs_ncm = bool(columns.get('ncm')) and not ncm
        has_text_to_review = bool(include_grammar_rows and (title or description))
        if not include_custom_task_rows and not has_text_to_review and not (needs_title or needs_description or needs_ncm):
            continue
        payload.append({
            'row_index': int(index),
            'sku': _value(row, columns.get('sku', '')),
            'brand': _value(row, columns.get('brand', '')),
            'category': _value(row, columns.get('category', '')),
            'title': title,
            'description': description,
            'ncm': ncm,
            'needs': {'title': needs_title, 'description': needs_description, 'ncm': needs_ncm, 'grammar': has_text_to_review},
            'row_data': _safe_row_data(row),
        })
    return payload


def _resolve_ai_column(item: dict[str, Any], field: str, columns: dict[str, str], df: pd.DataFrame) -> str:
    allowed = {'title': columns.get('title', ''), 'description': columns.get('description', ''), 'ncm': columns.get('ncm', '')}
    if field in allowed:
        return allowed.get(field, '')
    requested = clean_cell(item.get('column', ''))
    if not requested:
        return ''
    for column in df.columns:
        if str(column) == requested or normalize_key(str(column)) == normalize_key(requested):
            return str(column)
    return ''


def _normalize_suggestions(raw: list[dict[str, Any]], df: pd.DataFrame, columns: dict[str, str]) -> list[ProductAISuggestion]:
    suggestions: list[ProductAISuggestion] = []
    for item in raw:
        try:
            row_index = int(item.get('row_index'))
        except Exception:
            continue
        if row_index not in df.index:
            continue
        field = str(item.get('field') or '').strip().lower()
        if field == 'grammar_title':
            field = 'title'
        if field == 'grammar_description':
            field = 'description'
        column = _resolve_ai_column(item, field, columns, df)
        if not column:
            continue
        if field not in {'title', 'description', 'ncm'} and _is_protected_column(column):
            continue
        suggested = clean_cell(item.get('suggested', ''))
        if not suggested:
            continue
        if field == 'ncm' or normalize_key(column) == 'ncm':
            suggested = ''.join(ch for ch in suggested if ch.isdigit())[:8]
            if len(suggested) != 8:
                continue
            field = 'ncm'
        if field not in {'title', 'description', 'ncm'}:
            field = 'multitarefa'
        original = _value(df.loc[row_index], column)
        if original.strip() == suggested.strip():
            continue
        suggestions.append(
            ProductAISuggestion(
                row_index,
                _product_ref(df.loc[row_index], columns),
                field,
                column,
                original,
                suggested,
                clean_cell(item.get('reason', 'Sugestão gerada pela IA.')),
            )
        )
    return suggestions


def _call_openai_for_suggestions(
    df: pd.DataFrame,
    columns: dict[str, str],
    actions: dict[str, bool],
    max_rows: int,
    custom_task: str = '',
) -> list[ProductAISuggestion]:
    api_key = get_user_openai_key()
    if not api_key:
        return []
    clean_task = clean_cell(custom_task)
    wants_grammar = bool(actions.get('grammar'))
    rows = _rows_payload(df, columns, max_rows=max_rows, include_custom_task_rows=bool(clean_task), include_grammar_rows=wants_grammar)
    if not rows:
        return []
    enabled_actions = [name for name, enabled in actions.items() if enabled]
    if clean_task:
        enabled_actions.append('multitarefa')
    editable_columns = [str(column) for column in df.columns if not _is_protected_column(str(column))]
    system = (
        'Você é uma IA de revisão de catálogo para o Mapeia.AI. '
        'Melhore dados de produtos sem inventar especificações técnicas. Use somente dados da linha fornecida. '
        'Para NCM, gere apenas sugestão de 8 dígitos quando houver contexto suficiente. '
        'Nunca altere preço, GTIN/EAN, estoque, depósito, código/SKU, ID, imagens ou URLs. '
        'Quando a ação grammar estiver ligada, corrija apenas ortografia, acentos, pontuação, capitalização e gramática do título e da descrição, sem mudar o sentido comercial do produto. '
        'Quando receber tarefa livre, converta em sugestões linha a linha, sempre apontando uma coluna existente e segura.'
    )
    user = {
        'enabled_actions': enabled_actions,
        'custom_task': clean_task,
        'editable_columns_for_custom_task': editable_columns,
        'protected_columns_rule': 'Não sugerir alterações em colunas críticas como preço, GTIN/EAN, estoque, depósito, código/SKU, ID, imagens ou URLs.',
        'rules': [
            'title: reformular ou criar título curto, claro e comercial, sem inventar voltagem, cor, tamanho ou compatibilidade.',
            'description: melhorar descrição complementar com texto limpo, profissional e fiel ao conteúdo existente.',
            'grammar: corrigir somente ortografia e gramática de title e description existentes, sem criar características novas.',
            'ncm: sugerir NCM de 8 dígitos somente quando estiver vazio e houver contexto mínimo.',
            'multitarefa: atender o pedido livre do usuário somente em colunas editáveis e existentes.',
            'Retorne apenas JSON.',
        ],
        'rows': rows,
        'output_schema': {
            'suggestions': [
                {
                    'row_index': 0,
                    'field': 'title | description | grammar_title | grammar_description | ncm | multitarefa',
                    'column': 'obrigatório para multitarefa; opcional para title/description/ncm',
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
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    parsed = _safe_json_loads(data['choices'][0]['message']['content'])
    raw = parsed.get('suggestions', [])
    return _normalize_suggestions(raw if isinstance(raw, list) else [], df, columns)


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
    custom_task: str = '',
) -> tuple[list[ProductAISuggestion], str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return [], 'Sem dados finais para revisar.'
    selected_actions = actions or {'title': True, 'description': True, 'ncm': True, 'grammar': False}
    clean_task = clean_cell(custom_task)
    columns = detect_product_columns(df)
    if not any(columns.get(key) for key in ['title', 'description', 'ncm']) and not clean_task:
        return [], 'Não encontrei colunas de título, descrição complementar ou NCM na planilha final.'
    try:
        suggestions = _call_openai_for_suggestions(df, columns, selected_actions, max_rows=max_rows, custom_task=clean_task)
        if suggestions:
            return suggestions, 'Sugestões geradas pela IA conectada' + (' com multitarefa.' if clean_task else '.')
        if ai_ready():
            return [], 'A IA conectou, mas não encontrou alterações seguras para sugerir.'
    except Exception as exc:
        local = _fallback_suggestions(df, columns, selected_actions, max_rows=max_rows)
        if local:
            return local, f'IA online falhou ({exc}). Mostrei sugestões locais seguras.'
        return [], f'IA online falhou: {exc}'
    local = _fallback_suggestions(df, columns, selected_actions, max_rows=max_rows)
    if local:
        return local, 'Chave OpenAI não informada no sidebar. Mostrei sugestões locais seguras.'
    if clean_task or bool(selected_actions.get('grammar')):
        return [], 'Chave OpenAI não informada no sidebar. Ortografia/gramática e multitarefa livre precisam da IA conectada.'
    return [], 'Chave OpenAI não informada no sidebar e não encontrei sugestões locais seguras.'


def suggestions_to_dataframe(suggestions: list[ProductAISuggestion]) -> pd.DataFrame:
    return pd.DataFrame([
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
    ])


def apply_product_ai_suggestions(df: pd.DataFrame, edited_suggestions: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if not isinstance(edited_suggestions, pd.DataFrame) or edited_suggestions.empty:
        return out
    for _, row in edited_suggestions.iterrows():
        if not bool(row.get('Aplicar', False)):
            continue
        try:
            row_index = int(row.get('Linha'))
        except Exception:
            continue
        column = str(row.get('Coluna') or '').strip()
        suggested = clean_cell(row.get('Sugestão IA', ''))
        if row_index not in out.index or column not in out.columns or not suggested:
            continue
        if _is_protected_column(column) and normalize_key(column) != 'ncm':
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
