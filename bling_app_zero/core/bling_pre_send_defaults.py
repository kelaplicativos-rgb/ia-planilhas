from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_pre_send_defaults.py'

_NAME_FIELDS = ('nome', 'Nome', 'produto', 'Produto', 'titulo', 'Título', 'título', 'descricao produto', 'Descrição produto', 'descricao_produto')
_DESC_FIELDS = ('descricao', 'Descrição', 'descrição', 'descricao_curta', 'Descrição Curta', 'descrição curta', 'detalhes', 'Detalhes')
_CODE_FIELDS = ('codigo', 'Código', 'código', 'sku', 'SKU', 'gtin', 'GTIN', 'ean', 'EAN')


def _clean(value: object) -> str:
    text = str(value or '').strip()
    if text.lower() in {'nan', 'none', 'null'}:
        return ''
    return ' '.join(text.split())


def _first(data: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    lowered = {str(k).lower(): k for k in data.keys()}
    for field in fields:
        if field in data:
            value = _clean(data.get(field))
            if value:
                return value
        key = lowered.get(field.lower())
        if key is not None:
            value = _clean(data.get(key))
            if value:
                return value
    return ''


def _target_key(data: Mapping[str, Any], preferred: str, aliases: tuple[str, ...]) -> str:
    lowered = {str(k).lower(): str(k) for k in data.keys()}
    for alias in aliases:
        key = lowered.get(alias.lower())
        if key:
            return key
    return preferred


def apply_product_send_defaults(row: Any) -> dict[str, Any]:
    """Preenche defaults mínimos antes da pré-decisão inteligente.

    Objetivo: impedir que produto com descrição/código/preço válidos seja
    bloqueado antes dos motores de payload/upsert atuarem. Não inventa imagem;
    imagem ausente vira aviso, não bloqueio automático.
    """
    try:
        data = dict(row.to_dict()) if hasattr(row, 'to_dict') else dict(row or {})
    except Exception:
        return row

    nome = _first(data, _NAME_FIELDS)
    descricao = _first(data, _DESC_FIELDS)
    codigo = _first(data, _CODE_FIELDS)

    if not nome:
        fallback = descricao or codigo
        if fallback:
            key = _target_key(data, 'nome', _NAME_FIELDS)
            data[key] = fallback[:120]

    if not descricao and nome:
        key = _target_key(data, 'descricao', _DESC_FIELDS)
        data[key] = nome

    return data


def apply_dataframe_send_defaults(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    rows = [apply_product_send_defaults(row) for _idx, row in df.fillna('').iterrows()]
    return pd.DataFrame(rows, columns=list(df.columns)).fillna('') if rows else df


__all__ = ['RESPONSIBLE_FILE', 'apply_dataframe_send_defaults', 'apply_product_send_defaults']
