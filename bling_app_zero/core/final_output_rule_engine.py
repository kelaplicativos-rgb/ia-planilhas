from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.final_download_resources import (
    MAX_IMAGE_URLS_PER_PRODUCT,
    image_url_parts,
    limit_bling_images_resource,
    looks_like_image_column,
    normalize_image_separator_resource,
)
from bling_app_zero.core.final_measure_unit_defaults import apply_measure_unit_default_resource
from bling_app_zero.core.final_video_link_guard import apply_video_link_guard_resource
from bling_app_zero.core.text import normalize_key
from bling_app_zero.core.user_rules import get_user_rules

RESPONSIBLE_FILE = 'bling_app_zero/core/final_output_rule_engine.py'
EMPTY_VALUES = {'', 'nan', 'none', 'null', '<na>', 'na', 'n/a'}
TITLE_TARGET_TERMS = ('nome', 'titulo', 'título', 'title', 'name')
TITLE_SOURCE_TERMS = ('descricao', 'descrição', 'produto', 'titulo', 'título', 'nome', 'title', 'name')
BAD_TITLE_SOURCE_TERMS = ('preco', 'preço', 'valor', 'estoque', 'saldo', 'quantidade', 'qtd', 'codigo', 'código', 'sku', 'gtin', 'ean', 'url', 'link', 'imagem', 'foto', 'marca', 'categoria', 'ncm', 'deposito')


@dataclass(frozen=True)
class FinalOutputRuleReport:
    context: str
    normalize_images_enabled: bool
    limit_images_enabled: bool
    image_columns: tuple[str, ...]
    measure_unit_columns: tuple[str, ...]
    measure_unit_cells_changed: int
    measure_unit_value: str
    video_link_columns: tuple[str, ...]
    video_links_removed: int
    video_link_cells_changed: int
    rows_over_image_limit_before: int
    rows_over_image_limit_after: int
    rows_limited: int
    changed_cells: int
    warnings: tuple[str, ...]
    blocked_for_api: bool
    responsible_file: str = RESPONSIBLE_FILE

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['image_columns'] = list(self.image_columns)
        data['measure_unit_columns'] = list(self.measure_unit_columns)
        data['video_link_columns'] = list(self.video_link_columns)
        data['warnings'] = list(self.warnings)
        return data


def _safe_df(df: pd.DataFrame | None) -> pd.DataFrame:
    return df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _clean(value: Any) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '').replace('\x00', '').replace('\xa0', ' ')
    text = text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    return ' '.join(text.split()).strip()


def _is_empty(value: Any) -> bool:
    return normalize_key(_clean(value)) in EMPTY_VALUES


def _has_term(column: Any, terms: tuple[str, ...]) -> bool:
    key = normalize_key(column)
    return any(normalize_key(term) in key for term in terms if normalize_key(term))


def _title_from_text(value: Any, limit: int = 120) -> str:
    text = _clean(value)
    if _is_empty(text):
        return ''
    for sep in (' — ', ' – ', ' - ', ' | ', ' • ', '—', '–'):
        if sep in text:
            out = _clean(text.split(sep, 1)[0])
            if len(out) >= 3:
                return out[:limit].strip()
    out = _clean(re.split(r'(?<=[.!?])\s+', text, maxsplit=1)[0])
    return out if len(out) <= limit else _clean(out[:limit].rsplit(' ', 1)[0])


def _title_columns(df: pd.DataFrame) -> list[str]:
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        return []
    out: list[str] = []
    for column in df.columns:
        key = normalize_key(column)
        if any(term in key for term in ('ingrediente', 'metodo', 'preparo', 'complementar')):
            continue
        if _has_term(column, TITLE_TARGET_TERMS):
            out.append(str(column))
    return out


def _title_sources(df: pd.DataFrame, title_columns: list[str]) -> list[str]:
    if not isinstance(df, pd.DataFrame) or not len(df.columns):
        return []
    out: list[str] = []
    for column in df.columns:
        text = str(column)
        if text in title_columns or _has_term(text, BAD_TITLE_SOURCE_TERMS):
            continue
        if _has_term(text, TITLE_SOURCE_TERMS):
            out.append(text)
    for column in df.columns:
        text = str(column)
        if text not in title_columns and text not in out and not _has_term(text, BAD_TITLE_SOURCE_TERMS):
            out.append(text)
    return out


def title_guard_empty_rows(df: pd.DataFrame | None) -> list[int]:
    out = _safe_df(df)
    titles = _title_columns(out)
    if out.empty or not titles:
        return []
    rows: list[int] = []
    for pos, (_idx, row) in enumerate(out.fillna('').astype(str).iterrows(), start=1):
        if not any(not _is_empty(row.get(col, '')) for col in titles):
            rows.append(pos)
    return rows


def apply_final_title_guard(df: pd.DataFrame | None, *, context: str = 'download') -> tuple[pd.DataFrame, int, tuple[int, ...]]:
    out = _safe_df(df)
    titles = _title_columns(out)
    sources = _title_sources(out, titles)
    changed = 0
    if not out.empty and titles and sources:
        view = out.fillna('').astype(str)
        for idx, row in view.iterrows():
            for title_col in titles:
                if not _is_empty(row.get(title_col, '')):
                    continue
                value = ''
                for source_col in sources:
                    if source_col in row.index:
                        value = _title_from_text(row.get(source_col, ''))
                    if not _is_empty(value):
                        break
                if not _is_empty(value):
                    out.at[idx, title_col] = value
                    changed += 1
    empty_rows = tuple(title_guard_empty_rows(out))
    if changed or empty_rows:
        add_audit_event('final_title_guard_applied', area='FINAL_OUTPUT', status='OK' if not empty_rows else 'BLOQUEADO', details={'context': context, 'title_columns': titles, 'source_columns': sources[:30], 'changed_cells': changed, 'empty_rows_after': list(empty_rows[:50]), 'empty_rows_after_count': len(empty_rows), 'responsible_file': RESPONSIBLE_FILE})
    return out.copy().fillna(''), changed, empty_rows


def _image_columns(df: pd.DataFrame) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return [str(column) for column in df.columns if looks_like_image_column(column)]


def _row_has_image_excess(row: pd.Series, columns: list[str], *, max_images: int = MAX_IMAGE_URLS_PER_PRODUCT) -> bool:
    for column in columns:
        if column not in row.index:
            continue
        if len(image_url_parts(row.get(column, ''))) > max_images:
            return True
    return False


def rows_over_bling_image_limit(df: pd.DataFrame | None, *, max_images: int = MAX_IMAGE_URLS_PER_PRODUCT) -> list[Any]:
    out = _safe_df(df)
    columns = _image_columns(out)
    if out.empty or not columns:
        return []
    return [index for index, row in out.iterrows() if _row_has_image_excess(row, columns, max_images=max_images)]


def _changed_cells(before: pd.DataFrame, after: pd.DataFrame, columns: list[str]) -> int:
    if before.empty or after.empty or not columns:
        return 0
    total = 0
    for column in columns:
        if column not in before.columns or column not in after.columns:
            continue
        old_values = before[column].fillna('').astype(str).tolist()
        new_values = after[column].fillna('').astype(str).tolist()
        total += sum(1 for old, new in zip(old_values, new_values) if old != new)
    return total


def apply_final_output_rules(
    df: pd.DataFrame | None,
    *,
    context: str = 'download',
    block_api_when_rule_disabled: bool = True,
) -> tuple[pd.DataFrame, FinalOutputRuleReport]:
    original = _safe_df(df)
    current = original.copy()
    rules = get_user_rules()

    normalize_images_enabled = bool(rules.get('normalize_image_separator', True))
    limit_images_enabled = bool(rules.get('limit_bling_images', True))
    columns_before = _image_columns(current)
    excess_before = rows_over_bling_image_limit(current)

    if normalize_images_enabled:
        current = normalize_image_separator_resource(current, enabled=True, limit_to_bling_max=False).df

    video_result = apply_video_link_guard_resource(current)
    current = video_result.df

    if limit_images_enabled:
        current = limit_bling_images_resource(current, enabled=True).df

    measure_result = apply_measure_unit_default_resource(current, rules)
    current = measure_result.df

    current, title_filled, title_empty_rows = apply_final_title_guard(current, context=context)

    columns_after = _image_columns(current)
    excess_after = rows_over_bling_image_limit(current)
    changed_columns = sorted(set(columns_before + columns_after + list(measure_result.columns) + list(video_result.columns) + _title_columns(current)))
    changed = _changed_cells(original, current, changed_columns)
    rows_limited = max(0, len(excess_before) - len(excess_after)) if limit_images_enabled else 0

    warnings: list[str] = []
    blocked_for_api = False
    if excess_after and not limit_images_enabled:
        message = f'{len(excess_after)} produto(s) ainda têm mais de {MAX_IMAGE_URLS_PER_PRODUCT} imagens. A regra “Limitar imagens para Bling” está desligada.'
        warnings.append(message)
        if str(context or '').strip().lower() == 'api' and block_api_when_rule_disabled:
            blocked_for_api = True
            warnings.append('Envio por API bloqueado: o Bling pode recusar produtos com mais de 6 imagens.')

    if title_empty_rows:
        sample = ', '.join(map(str, list(title_empty_rows)[:12]))
        suffix = '...' if len(title_empty_rows) > 12 else ''
        warnings.append(f'{len(title_empty_rows)} produto(s) ainda estão sem título/nome. Linhas: {sample}{suffix}.')
        blocked_for_api = True
        warnings.append('Saída bloqueada: produto sem título pode cadastrar item errado no Bling.')

    if video_result.video_links_removed:
        warnings.append(f'{video_result.video_links_removed} link(s) de vídeo foram removidos do arquivo final.')

    if changed:
        add_audit_event(
            'final_output_rules_applied',
            area='FINAL_OUTPUT',
            status='OK',
            details={
                'context': context,
                'changed_cells': changed,
                'title_cells_filled': title_filled,
                'rows_over_image_limit_before': len(excess_before),
                'rows_over_image_limit_after': len(excess_after),
                'rows_limited': rows_limited,
                'normalize_image_separator': normalize_images_enabled,
                'limit_bling_images': limit_images_enabled,
                'image_columns': columns_after,
                'measure_unit_columns': list(measure_result.columns),
                'measure_unit_cells_changed': int(measure_result.changed),
                'measure_unit_value': measure_result.fill_value,
                'video_link_columns': list(video_result.columns),
                'video_links_removed': int(video_result.video_links_removed),
                'video_link_cells_changed': int(video_result.changed),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    elif warnings:
        add_audit_event(
            'final_output_rules_warning',
            area='FINAL_OUTPUT',
            status='BLOQUEADO' if blocked_for_api else 'AVISO',
            details={
                'context': context,
                'warnings': warnings,
                'rows_over_image_limit_before': len(excess_before),
                'rows_over_image_limit_after': len(excess_after),
                'limit_bling_images': limit_images_enabled,
                'image_columns': columns_before,
                'measure_unit_columns': list(measure_result.columns),
                'video_link_columns': list(video_result.columns),
                'video_links_removed': int(video_result.video_links_removed),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

    report = FinalOutputRuleReport(
        context=str(context or 'download'),
        normalize_images_enabled=normalize_images_enabled,
        limit_images_enabled=limit_images_enabled,
        image_columns=tuple(columns_after or columns_before),
        measure_unit_columns=tuple(measure_result.columns),
        measure_unit_cells_changed=int(measure_result.changed),
        measure_unit_value=measure_result.fill_value,
        video_link_columns=tuple(video_result.columns),
        video_links_removed=int(video_result.video_links_removed),
        video_link_cells_changed=int(video_result.changed),
        rows_over_image_limit_before=len(excess_before),
        rows_over_image_limit_after=len(excess_after),
        rows_limited=rows_limited,
        changed_cells=changed,
        warnings=tuple(warnings),
        blocked_for_api=blocked_for_api,
    )
    return current.copy().fillna(''), report


__all__ = [
    'FinalOutputRuleReport',
    'apply_final_output_rules',
    'apply_final_title_guard',
    'extract_title_from_text',
    'rows_over_bling_image_limit',
    'title_guard_empty_rows',
]
