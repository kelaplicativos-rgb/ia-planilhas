from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Mapping

import pandas as pd

EMPTY_MARKERS = {'nan', 'none', 'null', '<na>', 'n/a', 'na'}
IMAGE_COLUMN_TERMS = ('imagem', 'imagens', 'image', 'images', 'foto', 'fotos', 'url imagens')
GTIN_COLUMN_TERMS = ('gtin', 'ean', 'código de barras', 'codigo de barras')
URL_PATTERN = re.compile(r'https?://[^\s|;,]+', re.IGNORECASE)
DEFAULT_WEIGHT_VALUE = '0.300'


# Regras opcionais do fluxo universal.
# Importante: o grupo principal de regras continua controlando quando os defaults
# serão aplicados. Quando o grupo estiver ligado, pesos de cadastro nascem com o
# padrão seguro solicitado para evitar mapeamento manual desnecessário.
def default_smart_rules_config() -> dict[str, Any]:
    return {
        'enabled': False,
        'clean_text': False,
        'remove_empty_markers': False,
        'normalize_images': False,
        'dedupe_images': False,
        'limit_images': False,
        'max_images': 6,
        'validate_gtin': False,
        'fill_category_aliases': False,
        'apply_unit_default': False,
        'unit_value': 'UN',
        'apply_measure_unit_default': False,
        'measure_unit_value': 'Centímetros',
        'apply_status_default': False,
        'status_value': 'Ativo',
        'apply_condition_default': False,
        'condition_value': 'Novo',
        'apply_dimensions_default': False,
        'height_value': '2',
        'width_value': '11',
        'depth_value': '16',
        'apply_weight_default': True,
        'gross_weight_value': DEFAULT_WEIGHT_VALUE,
        'net_weight_value': DEFAULT_WEIGHT_VALUE,
        'overwrite_existing_fixed_values': False,
    }


def _clean_text(value: Any) -> str:
    text = '' if value is None else str(value)
    text = text.replace('\ufeff', '').replace('\x00', '').replace('\xa0', ' ')
    return ' '.join(text.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ').split()).strip()


def _norm(value: Any) -> str:
    return _clean_text(value).casefold()


def _column_key(value: Any) -> str:
    text = unicodedata.normalize('NFKD', _norm(value))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _is_column(column: Any, terms: tuple[str, ...]) -> bool:
    name = _norm(column)
    return any(term in name for term in terms)


def _is_empty_marker(value: Any) -> bool:
    return _norm(value) in EMPTY_MARKERS


def _split_images(value: Any) -> list[str]:
    raw = '' if value is None else str(value)
    text = _clean_text(raw)
    if not text:
        return []

    urls = [_clean_text(match.group(0)) for match in URL_PATTERN.finditer(raw)]
    if urls:
        return [url for url in urls if url]

    if '|' in raw:
        parts = raw.split('|')
    elif '\n' in raw or '\r' in raw:
        parts = raw.replace('\r', '\n').splitlines()
    elif ',' in raw or ';' in raw:
        parts = re.split(r'[,;]+', raw)
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


def _is_unit_abbreviation_column(column: Any) -> bool:
    key = _column_key(column)
    if 'medida' in key:
        return False
    return key in {'unidade', 'unid', 'und', 'un'} or key.endswith(' unidade')


def _is_measure_unit_column(column: Any) -> bool:
    key = _column_key(column)
    return key in {'unidade de medida', 'unidade medida', 'medida unidade'} or ('unidade' in key and 'medida' in key)


def _is_status_column(column: Any) -> bool:
    key = _column_key(column)
    return key in {'situacao', 'status'} or key.endswith(' situacao') or key.endswith(' status')


def _is_condition_column(column: Any) -> bool:
    key = _column_key(column)
    return key in {'condicao', 'condicao do produto', 'estado do produto'} or key.endswith(' condicao')


def _is_height_column(column: Any) -> bool:
    return 'altura' in _column_key(column)


def _is_width_column(column: Any) -> bool:
    key = _column_key(column)
    return 'largura' in key or key in {'l'}


def _is_depth_column(column: Any) -> bool:
    key = _column_key(column)
    return 'profundidade' in key or 'comprimento' in key or key in {'p'}


def _is_gross_weight_column(column: Any) -> bool:
    key = _column_key(column)
    return 'peso bruto' in key or key == 'peso bruto kg'


def _is_net_weight_column(column: Any) -> bool:
    key = _column_key(column)
    return 'peso liquido' in key or 'peso líquido' in _norm(column) or key == 'peso liquido kg'


def _fill_default(series: pd.Series, value: Any, *, overwrite: bool) -> pd.Series:
    default_value = _clean_text(value)
    if not default_value:
        return series
    out = series.copy()
    if overwrite:
        mask = pd.Series([True] * len(out), index=out.index)
    else:
        mask = out.map(lambda item: _clean_text(item) == '' or _is_empty_marker(item))
    if bool(mask.any()):
        out.loc[mask] = default_value
    return out


def _apply_optional_defaults(column: Any, series: pd.Series, rules: Mapping[str, Any]) -> tuple[pd.Series, str]:
    overwrite = bool(rules.get('overwrite_existing_fixed_values'))
    if bool(rules.get('apply_measure_unit_default')) and _is_measure_unit_column(column):
        return _fill_default(series, rules.get('measure_unit_value'), overwrite=overwrite), 'measure_unit'
    if bool(rules.get('apply_unit_default')) and _is_unit_abbreviation_column(column):
        return _fill_default(series, rules.get('unit_value'), overwrite=overwrite), 'unit'
    if bool(rules.get('apply_status_default')) and _is_status_column(column):
        return _fill_default(series, rules.get('status_value'), overwrite=overwrite), 'status'
    if bool(rules.get('apply_condition_default')) and _is_condition_column(column):
        return _fill_default(series, rules.get('condition_value'), overwrite=overwrite), 'condition'
    if bool(rules.get('apply_dimensions_default')) and _is_height_column(column):
        return _fill_default(series, rules.get('height_value'), overwrite=overwrite), 'height'
    if bool(rules.get('apply_dimensions_default')) and _is_width_column(column):
        return _fill_default(series, rules.get('width_value'), overwrite=overwrite), 'width'
    if bool(rules.get('apply_dimensions_default')) and _is_depth_column(column):
        return _fill_default(series, rules.get('depth_value'), overwrite=overwrite), 'depth'
    if bool(rules.get('apply_weight_default')) and _is_gross_weight_column(column):
        return _fill_default(series, rules.get('gross_weight_value'), overwrite=overwrite), 'gross_weight'
    if bool(rules.get('apply_weight_default')) and _is_net_weight_column(column):
        return _fill_default(series, rules.get('net_weight_value'), overwrite=overwrite), 'net_weight'
    return series, ''


def normalize_smart_rules_config(config: Mapping[str, Any] | None, *, enabled: bool | None = None) -> dict[str, Any]:
    base = default_smart_rules_config()
    if isinstance(config, Mapping):
        base.update(dict(config))
    if enabled is not None:
        base['enabled'] = bool(enabled)
    base['max_images'] = max(0, int(base.get('max_images') or 0))
    if not _clean_text(base.get('gross_weight_value')):
        base['gross_weight_value'] = DEFAULT_WEIGHT_VALUE
    if not _clean_text(base.get('net_weight_value')):
        base['net_weight_value'] = DEFAULT_WEIGHT_VALUE
    base['overwrite_existing_fixed_values'] = False
    return base


def _rule_kind_for_column(column: Any, rules: Mapping[str, Any]) -> str:
    if not bool(rules.get('enabled')):
        return ''
    if bool(rules.get('apply_measure_unit_default')) and _clean_text(rules.get('measure_unit_value')) and _is_measure_unit_column(column):
        return 'measure_unit'
    if bool(rules.get('apply_unit_default')) and _clean_text(rules.get('unit_value')) and _is_unit_abbreviation_column(column):
        return 'unit'
    if bool(rules.get('apply_status_default')) and _clean_text(rules.get('status_value')) and _is_status_column(column):
        return 'status'
    if bool(rules.get('apply_condition_default')) and _clean_text(rules.get('condition_value')) and _is_condition_column(column):
        return 'condition'
    if bool(rules.get('apply_dimensions_default')) and _clean_text(rules.get('height_value')) and _is_height_column(column):
        return 'height'
    if bool(rules.get('apply_dimensions_default')) and _clean_text(rules.get('width_value')) and _is_width_column(column):
        return 'width'
    if bool(rules.get('apply_dimensions_default')) and _clean_text(rules.get('depth_value')) and _is_depth_column(column):
        return 'depth'
    if bool(rules.get('apply_weight_default')) and _clean_text(rules.get('gross_weight_value')) and _is_gross_weight_column(column):
        return 'gross_weight'
    if bool(rules.get('apply_weight_default')) and _clean_text(rules.get('net_weight_value')) and _is_net_weight_column(column):
        return 'net_weight'
    return ''


def rule_managed_target_columns(columns: Iterable[Any], config: Mapping[str, Any] | None = None) -> list[str]:
    """Retorna colunas do contrato que serão preenchidas por regras fixas.

    Essas colunas não devem aparecer para mapeamento manual/IA, porque o valor
    final será aplicado pelo painel de regras no preview/download.
    """
    rules = normalize_smart_rules_config(config)
    return [str(column) for column in columns or [] if _rule_kind_for_column(column, rules)]


def rule_managed_source_mapping(source_columns: Iterable[Any], target_columns: Iterable[Any], config: Mapping[str, Any] | None = None) -> dict[str, str]:
    """Liga campos de regra à origem equivalente sem expor ao usuário.

    A regra continua sendo fallback por célula: valores que já vieram preenchidos
    na origem são preservados; somente células vazias recebem o padrão definido.
    """
    rules = normalize_smart_rules_config(config)
    if not bool(rules.get('enabled')):
        return {}

    source_names = [str(column) for column in source_columns or []]
    source_by_exact_key: dict[str, str] = {}
    source_by_rule_kind: dict[str, str] = {}
    for source in source_names:
        source_by_exact_key.setdefault(_column_key(source), source)
        source_kind = _rule_kind_for_column(source, rules)
        if source_kind:
            source_by_rule_kind.setdefault(source_kind, source)

    mapping: dict[str, str] = {}
    for target in target_columns or []:
        target_name = str(target)
        target_kind = _rule_kind_for_column(target_name, rules)
        if not target_kind:
            continue
        selected = source_by_exact_key.get(_column_key(target_name)) or source_by_rule_kind.get(target_kind, '')
        if selected:
            mapping[target_name] = selected
    return mapping


def apply_universal_smart_rules(df: pd.DataFrame, config: Mapping[str, Any] | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    rules = normalize_smart_rules_config(config)
    if not isinstance(df, pd.DataFrame) or df.empty or not rules.get('enabled'):
        return df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame(), {
            'enabled': bool(rules.get('enabled')),
            'applied_cells': 0,
            'image_columns': [],
            'gtin_columns': [],
            'fixed_columns': [],
        }

    out = df.copy().fillna('')
    applied_cells = 0
    image_columns: list[str] = []
    gtin_columns: list[str] = []
    fixed_columns: list[dict[str, str]] = []

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

        updated, fixed_kind = _apply_optional_defaults(column, updated, rules)
        if fixed_kind:
            fixed_columns.append({'column': str(column), 'rule': fixed_kind})

        applied_cells += int((updated.astype(str) != original.astype(str)).sum())
        out[column] = updated

    report = {
        'enabled': True,
        'applied_cells': applied_cells,
        'image_columns': image_columns,
        'gtin_columns': gtin_columns,
        'fixed_columns': fixed_columns,
        'limit_images': bool(rules.get('limit_images')),
        'max_images': int(rules.get('max_images') or 0),
        'validate_gtin': bool(rules.get('validate_gtin')),
        'fill_category_aliases': bool(rules.get('fill_category_aliases')),
    }
    return out, report


__all__ = [
    'apply_universal_smart_rules',
    'default_smart_rules_config',
    'normalize_smart_rules_config',
    'rule_managed_source_mapping',
    'rule_managed_target_columns',
]
