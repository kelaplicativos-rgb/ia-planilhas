from __future__ import annotations

import re
from typing import Any, Mapping

import pandas as pd

EMPTY_MARKERS = {'nan', 'none', 'null', '<na>', 'n/a', 'na'}
IMAGE_COLUMN_TERMS = ('imagem', 'imagens', 'image', 'images', 'foto', 'fotos', 'url imagens')
GTIN_COLUMN_TERMS = ('gtin', 'ean', 'código de barras', 'codigo de barras')


def _clean_text(value: Any) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '').replace('\x00', '').replace('\xa0', ' ')
    return ' '.join(text.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ').split()).strip()


def _norm(value: Any) -> str:
    return _clean_text(value).casefold()


def _is_column(column: Any, terms: tuple[str, ...]) -> bool:
    name = _norm(column)
    return any(term in name for term in terms)


def _is_empty_marker(value: Any) -> bool:
    return _norm(value) in EMPTY_MARKERS


def _split_images(value: Any) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []
    if '|' in text:
        parts = text.split('|')
    elif '\n' in str(value):
        parts = str(value).splitlines()
    else:
        parts = [text]
    return [_clean_text(part) for part in parts if _clean_text(part)]


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _normalize_image_value(value: Any, *, limit_enabled: bool, max_images: int, dedupe: bool) -> str:
    images = _split_images(value)
    if dedupe:
        images = _dedupe_keep_order(images)
    if limit_enabled:
        images = images[: max(0, int(max_images or 0))]
    return '|'.join(images)


def _ean_checksum_ok(digits: str) -> bool:
    if not digits.isdigit() or len(digits) not in {8, 12, 13, 14}:
        return False
    body = digits[:-1]
    check = int(digits[-1])
    total = 0
    for index, char in enumerate(reversed(body), start=1):
        total += int(char) * (3 if index % 2 == 1 else 1)
    return (10 - (total % 10)) % 10 == check


def _normalize_gtin(value: Any, *, validate: bool) -> str:
    text = _clean_text(value)
    digits = re.sub(r'\D+', '', text)
    if not digits:
        return ''
    if not validate:
        return digits
    return digits if _ean_checksum_ok(digits) else ''


def default_smart_rules_config() -> dict[str, Any]:
    return {
        'enabled': False,
        'clean_text': True,
        'remove_empty_markers': True,
        'normalize_images': True,
        'dedupe_images': True,
        'limit_images': False,
        'max_images': 6,
        'validate_gtin': False,
    }


def normalize_smart_rules_config(config: Mapping[str, Any] | None, *, enabled: bool | None = None) -> dict[str, Any]:
    base = default_smart_rules_config()
    if isinstance(config, Mapping):
        base.update(dict(config))
    if enabled is not None:
        base['enabled'] = bool(enabled)
    base['max_images'] = max(0, int(base.get('max_images') or 0))
    return base


def apply_universal_smart_rules(df: pd.DataFrame, config: Mapping[str, Any] | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    rules = normalize_smart_rules_config(config)
    if not isinstance(df, pd.DataFrame) or df.empty or not rules.get('enabled'):
        return df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame(), {'enabled': bool(rules.get('enabled')), 'applied_cells': 0, 'image_columns': [], 'gtin_columns': []}

    out = df.copy().fillna('')
    applied_cells = 0
    image_columns: list[str] = []
    gtin_columns: list[str] = []

    for column in out.columns:
        original = out[column].astype(str)
        updated = original.copy()

        if rules.get('clean_text'):
            updated = updated.map(_clean_text)
        if rules.get('remove_empty_markers'):
            updated = updated.map(lambda value: '' if _is_empty_marker(value) else value)

        if rules.get('normalize_images') and _is_column(column, IMAGE_COLUMN_TERMS):
            image_columns.append(str(column))
            updated = updated.map(
                lambda value: _normalize_image_value(
                    value,
                    limit_enabled=bool(rules.get('limit_images')),
                    max_images=int(rules.get('max_images') or 0),
                    dedupe=bool(rules.get('dedupe_images')),
                )
            )

        if rules.get('validate_gtin') and _is_column(column, GTIN_COLUMN_TERMS):
            gtin_columns.append(str(column))
            updated = updated.map(lambda value: _normalize_gtin(value, validate=True))

        applied_cells += int((updated.astype(str) != original.astype(str)).sum())
        out[column] = updated

    report = {
        'enabled': True,
        'applied_cells': applied_cells,
        'image_columns': image_columns,
        'gtin_columns': gtin_columns,
        'limit_images': bool(rules.get('limit_images')),
        'max_images': int(rules.get('max_images') or 0),
        'validate_gtin': bool(rules.get('validate_gtin')),
    }
    return out, report


__all__ = ['apply_universal_smart_rules', 'default_smart_rules_config', 'normalize_smart_rules_config']
