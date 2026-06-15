from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd

MAX_BLING_IMAGES = 6
IMAGE_SEPARATOR = '|'
IMAGE_COLUMN_HINTS = (
    'imagem',
    'imagens',
    'image',
    'images',
    'foto',
    'fotos',
    'midia',
    'mídia',
    'url imagem',
    'url imagens',
)
PRODUCT_NAME_HINTS = (
    'descrição',
    'descricao',
    'nome',
    'produto',
    'título',
    'titulo',
    'name',
    'title',
)
_SPLIT_RE = re.compile(r'[|;\n\r]+')


@dataclass(frozen=True)
class ImageLimitReport:
    image_columns: list[str]
    products_with_excess: int
    images_removed: int
    rows: list[dict[str, Any]]

    @property
    def has_issues(self) -> bool:
        return bool(self.rows)

    def as_dataframe(self) -> pd.DataFrame:
        if not self.rows:
            return pd.DataFrame(
                columns=[
                    'Linha',
                    'Produto',
                    'Coluna',
                    'Imagens antes',
                    'Imagens depois',
                    'Removidas',
                    'Mantidas',
                    'Ignoradas',
                ]
            )
        return pd.DataFrame(self.rows)


def _safe_text(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    return str(value).strip()


def _looks_like_url(value: Any) -> bool:
    text = _safe_text(value).lower()
    return text.startswith('http://') or text.startswith('https://')


def _split_images(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        raw_items = [str(item).strip() for item in value]
    else:
        text = _safe_text(value)
        if not text:
            return []
        raw_items = [part.strip() for part in _SPLIT_RE.split(text)]
    return [item for item in raw_items if item]


def _dedupe_keep_order(items: list[str]) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for item in items:
        marker = item.strip()
        if not marker or marker in seen:
            continue
        seen.add(marker)
        kept.append(marker)
    return kept


def limit_image_value(value: Any, max_images: int = MAX_BLING_IMAGES) -> tuple[str, int, int]:
    items = _split_images(value)
    if not items:
        return _safe_text(value), 0, 0
    unique = _dedupe_keep_order(items)
    limited = unique[:max_images]
    removed = max(0, len(items) - len(limited))
    return IMAGE_SEPARATOR.join(limited), len(items), removed


def _is_image_column(df: pd.DataFrame, column: Any) -> bool:
    name = _safe_text(column).lower()
    if any(hint in name for hint in IMAGE_COLUMN_HINTS):
        return True
    try:
        sample = df[column].dropna().astype(str).head(40).tolist()
    except Exception:
        return False
    if not sample:
        return False
    hits = 0
    for value in sample:
        parts = _split_images(value)
        if len(parts) > 1 and any(_looks_like_url(part) for part in parts):
            hits += 1
        elif _looks_like_url(value):
            hits += 1
    return hits >= 2


def find_image_columns(df: pd.DataFrame) -> list[str]:
    if df is None or not hasattr(df, 'columns'):
        return []
    columns: list[str] = []
    for column in df.columns:
        if _is_image_column(df, column):
            columns.append(str(column))
    return columns


def _product_column(df: pd.DataFrame) -> str | None:
    for column in df.columns:
        name = _safe_text(column).lower()
        if any(hint == name or hint in name for hint in PRODUCT_NAME_HINTS):
            return str(column)
    return str(df.columns[0]) if len(df.columns) else None


def _preview_text(items: list[str], limit: int = 3) -> str:
    if not items:
        return ''
    preview = items[:limit]
    suffix = ' ...' if len(items) > limit else ''
    return IMAGE_SEPARATOR.join(preview) + suffix


def analyze_bling_image_limit(df: pd.DataFrame, max_images: int = MAX_BLING_IMAGES) -> ImageLimitReport:
    if df is None or not hasattr(df, 'columns'):
        return ImageLimitReport([], 0, 0, [])

    image_columns = find_image_columns(df)
    product_col = _product_column(df)
    rows: list[dict[str, Any]] = []
    total_removed = 0
    product_rows: set[int] = set()

    for column in image_columns:
        if column not in df.columns:
            continue
        for row_index, value in df[column].items():
            items = _split_images(value)
            if not items:
                continue
            unique = _dedupe_keep_order(items)
            limited = unique[:max_images]
            removed_items = items[len(limited):] if len(items) > len(limited) else []
            removed_count = max(0, len(items) - len(limited))
            has_duplicates = len(unique) != len(items)
            has_excess = len(unique) > max_images or len(items) > max_images
            if not has_excess and not has_duplicates:
                continue
            product_name = ''
            if product_col and product_col in df.columns:
                try:
                    product_name = _safe_text(df.at[row_index, product_col])
                except Exception:
                    product_name = ''
            total_removed += removed_count
            try:
                display_line = int(row_index) + 2
            except Exception:
                display_line = str(row_index)
            try:
                product_rows.add(int(row_index))
            except Exception:
                pass
            rows.append(
                {
                    'Linha': display_line,
                    'Produto': product_name,
                    'Coluna': column,
                    'Imagens antes': len(items),
                    'Imagens depois': len(limited),
                    'Removidas': removed_count,
                    'Mantidas': _preview_text(limited),
                    'Ignoradas': _preview_text(removed_items),
                }
            )

    return ImageLimitReport(
        image_columns=image_columns,
        products_with_excess=len(product_rows) if product_rows else len(rows),
        images_removed=total_removed,
        rows=rows,
    )


def apply_bling_image_limit(df: pd.DataFrame, max_images: int = MAX_BLING_IMAGES) -> tuple[pd.DataFrame, ImageLimitReport]:
    report = analyze_bling_image_limit(df, max_images=max_images)
    if df is None or not hasattr(df, 'copy'):
        return df, report
    fixed = df.copy()
    for column in report.image_columns:
        if column not in fixed.columns:
            continue
        fixed[column] = fixed[column].apply(lambda value: limit_image_value(value, max_images=max_images)[0])
    return fixed, analyze_bling_image_limit(fixed, max_images=max_images)


__all__ = [
    'MAX_BLING_IMAGES',
    'ImageLimitReport',
    'analyze_bling_image_limit',
    'apply_bling_image_limit',
    'find_image_columns',
    'limit_image_value',
]
