from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.universal_smart_rules import default_smart_rules_config, normalize_smart_rules_config

RESPONSIBLE_FILE = 'bling_app_zero/ui/shared_rules_resources.py'
STATE_KEY_SUFFIX = 'rules_resources_config'
LOCKED_MAPPING_FIELDS_KEY = 'mapeiaai_locked_mapping_fields_v1'
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'
BOOLEAN_RULE_KEYS = (
    'clean_text',
    'remove_empty_markers',
    'normalize_images',
    'dedupe_images',
    'limit_images',
    'validate_gtin',
    'fill_category_aliases',
    'apply_unit_default',
    'apply_measure_unit_default',
    'apply_status_default',
    'apply_condition_default',
    'apply_dimensions_default',
)


def _detect_columns(df: pd.DataFrame, terms: tuple[str, ...]) -> list[str]:
    if not isinstance(df, pd.DataFrame):
        return []
    out: list[str] = []
    for column in df.columns:
        name = str(column or '').casefold()
        if any(term in name for term in terms):
            out.append(str(column))
    return out


def _clean_text(value: Any) -> str:
    return '' if value is None else ' '.join(str(value).replace('\xa0', ' ').split()).strip()


def _column_key(value: Any) -> str:
    text = unicodedata.normalize('NFKD', _clean_text(value).casefold())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _enable_all_rules(config: dict[str, Any]) -> dict[str, Any]:
    updated = {**default_smart_rules_config(), **dict(config or {})}
    updated['enabled'] = True
    for key in BOOLEAN_RULE_KEYS:
        updated[key] = True
    updated['max_images'] = int(updated.get('max_images') or 6) or 6
    return updated


def _seed_rule_widgets(key_prefix: str, config: dict[str, Any]) -> None:
    mapping = {
        'clean_text': f'{key_prefix}_rules_clean_text',
        'remove_empty_markers': f'{key_prefix}_rules_empty_markers',
        'normalize_images': f'{key_prefix}_rules_normalize_images',
        'dedupe_images': f'{key_prefix}_rules_dedupe_images',
        'limit_images': f'{key_prefix}_rules_limit_images',
        'validate_gtin': f'{key_prefix}_rules_validate_gtin',
        'fill_category_aliases': f'{key_prefix}_rules_fill_category_aliases',
        'apply_unit_default': f'{key_prefix}_rules_apply_unit_default',
        'apply_measure_unit_default': f'{key_prefix}_rules_apply_measure_unit_default',
        'apply_status_default': f'{key_prefix}_rules_apply_status_default',
        'apply_condition_default': f'{key_prefix}_rules_apply_condition_default',
        'apply_dimensions_default': f'{key_prefix}_rules_apply_dimensions_default',
    }
    for config_key, widget_key in mapping.items():
        st.session_state[widget_key] = bool(config.get(config_key))
    st.session_state[f'{key_prefix}_rules_max_images'] = int(config.get('max_images') or 6)


def _fixed(value: Any) -> str:
    text = _clean_text(value)
    return f'{FIXED_VALUE_PREFIX}{text}' if text else ''


def _first_source_column(source: pd.DataFrame, terms: tuple[str, ...]) -> str:
    columns = _detect_columns(source, terms)
    for column in columns:
        try:
            if source[column].astype(str).str.strip().ne('').any():
                return column
        except Exception:
            continue
    return columns[0] if columns else ''


def _target_columns(model: pd.DataFrame, matcher) -> list[str]:
    if not isinstance(model, pd.DataFrame):
        return []
    return [str(column) for column in model.columns if matcher(str(column))]


def _is_image_column(column: str) -> bool:
    key = _column_key(column)
    return any(term in key for term in ('imagem', 'imagens', 'image', 'foto', 'fotos', 'url imagens'))


def _is_gtin_column(column: str) -> bool:
    key = _column_key(column)
    return any(term in key for term in ('gtin', 'ean', 'codigo de barras'))


def _is_category_column(column: str) -> bool:
    key = _column_key(column)
    return key in {'categoria', 'category', 'categoria produto', 'categoria do produto'} or key.startswith('categoria ')


def _is_unit_column(column: str) -> bool:
    key = _column_key(column)
    return 'medida' not in key and (key in {'unidade', 'unid', 'und', 'un'} or key.endswith(' unidade'))


def _is_measure_unit_column(column: str) -> bool:
    key = _column_key(column)
    return 'unidade' in key and 'medida' in key


def _is_status_column(column: str) -> bool:
    key = _column_key(column)
    return key in {'situacao', 'status'} or key.endswith(' situacao') or key.endswith(' status')


def _is_condition_column(column: str) -> bool:
    key = _column_key(column)
    return key in {'condicao', 'condicao do produto', 'estado do produto'} or key.endswith(' condicao')


def _is_height_column(column: str) -> bool:
    return 'altura' in _column_key(column)


def _is_width_column(column: str) -> bool:
    key = _column_key(column)
    return 'largura' in key or key == 'l'


def _is_depth_column(column: str) -> bool:
    key = _column_key(column)
    return 'profundidade' in key or 'comprimento' in key or key == 'p'


def _add_locks(locked: dict[str, dict[str, str]], columns: list[str], value: str, reason: str, kind: str) -> None:
    if not value:
        return
    for column in columns:
        locked[str(column)] = {'value': str(value), 'reason': reason, 'kind': kind}


def _build_locked_mapping_fields(source: pd.DataFrame, model: pd.DataFrame, config: dict[str, Any]) -> dict[str, dict[str, str]]:
    locked: dict[str, dict[str, str]] = {}
    if not bool(config.get('enabled')) or not isinstance(model, pd.DataFrame):
        return locked

    if bool(config.get('normalize_images')) or bool(config.get('dedupe_images')) or bool(config.get('limit_images')):
        image_source = _first_source_column(source, ('imagem', 'imagens', 'image', 'foto', 'fotos', 'url imagens', 'url'))
        _add_locks(locked, _target_columns(model, _is_image_column), image_source, 'Imagens tratadas nas regras inteligentes', 'images')

    if bool(config.get('validate_gtin')):
        gtin_source = _first_source_column(source, ('gtin', 'ean', 'código de barras', 'codigo de barras'))
        _add_locks(locked, _target_columns(model, _is_gtin_column), gtin_source, 'GTIN/EAN validado nas regras inteligentes', 'gtin')

    if bool(config.get('fill_category_aliases')):
        category_source = _first_source_column(source, ('categoria do produto', 'categoria', 'category'))
        _add_locks(locked, _target_columns(model, _is_category_column), category_source, 'Categoria preenchida pelas regras inteligentes', 'category')

    if bool(config.get('apply_unit_default')):
        _add_locks(locked, _target_columns(model, _is_unit_column), _fixed(config.get('unit_value')), 'Unidade definida pelas regras inteligentes', 'unit')
    if bool(config.get('apply_measure_unit_default')):
        _add_locks(locked, _target_columns(model, _is_measure_unit_column), _fixed(config.get('measure_unit_value')), 'Unidade de medida definida pelas regras inteligentes', 'measure_unit')
    if bool(config.get('apply_status_default')):
        _add_locks(locked, _target_columns(model, _is_status_column), _fixed(config.get('status_value')), 'Situação/Status definido pelas regras inteligentes', 'status')
    if bool(config.get('apply_condition_default')):
        _add_locks(locked, _target_columns(model, _is_condition_column), _fixed(config.get('condition_value')), 'Condição definida pelas regras inteligentes', 'condition')
    if bool(config.get('apply_dimensions_default')):
        _add_locks(locked, _target_columns(model, _is_height_column), _fixed(config.get('height_value')), 'Altura definida pelas regras inteligentes', 'height')
        _add_locks(locked, _target_columns(model, _is_width_column), _fixed(config.get('width_value')), 'Largura definida pelas regras inteligentes', 'width')
        _add_locks(locked, _target_columns(model, _is_depth_column), _fixed(config.get('depth_value')), 'Profundidade definida pelas regras inteligentes', 'depth')

    return locked


def _store_locked_fields(key_prefix: str, locked: dict[str, dict[str, str]]) -> None:
    st.session_state[LOCKED_MAPPING_FIELDS_KEY] = dict(locked)
    st.session_state[f'{key_prefix}_locked_mapping_fields_v1'] = dict(locked)


def render_rules_resources_panel(
    source: pd.DataFrame,
    model: pd.DataFrame,
    *,
    enabled: bool,
    key_prefix: str = 'mapeiaai_universal',
) -> dict[str, Any]:
    state_key = f'{key_prefix}_{STATE_KEY_SUFFIX}'
    previous_enabled_key = f'{state_key}_previous_main_enabled'
    was_enabled = bool(st.session_state.get(previous_enabled_key))
    current = normalize_smart_rules_config(st.session_state.get(state_key), enabled=enabled)

    if not enabled:
        current['enabled'] = False
        st.session_state[state_key] = current
        st.session_state[previous_enabled_key] = False
        _store_locked_fields(key_prefix, {})
        return current

    if enabled and not was_enabled:
        current = _enable_all_rules(current)
        _seed_rule_widgets(key_prefix, current)

    st.markdown('### Regras e recursos inteligentes')
    st.caption('O toggle principal nasce desligado. Ao ligar, todas as regras internas entram ligadas; desative apenas o que não quiser aplicar.')

    image_cols = sorted(set(_detect_columns(source, ('imagem', 'image', 'foto', 'url')) + _detect_columns(model, ('imagem', 'image', 'foto', 'url'))))
    gtin_cols = sorted(set(_detect_columns(source, ('gtin', 'ean', 'código de barras', 'codigo de barras')) + _detect_columns(model, ('gtin', 'ean', 'código de barras', 'codigo de barras'))))

    with st.expander('Abrir regras e recursos inteligentes', expanded=True):
        st.markdown('#### Limpeza segura')
        clean_text = st.checkbox('Limpar espaços, quebras de linha e caracteres invisíveis', value=bool(current.get('clean_text')), key=f'{key_prefix}_rules_clean_text')
        remove_empty_markers = st.checkbox('Tratar nan / none / null como vazio', value=bool(current.get('remove_empty_markers')), key=f'{key_prefix}_rules_empty_markers')

        st.markdown('#### Imagens')
        st.caption('Colunas detectadas: ' + (', '.join(image_cols) if image_cols else 'nenhuma coluna de imagem detectada agora.'))
        normalize_images = st.checkbox('Padronizar imagens usando separador |', value=bool(current.get('normalize_images')), key=f'{key_prefix}_rules_normalize_images')
        dedupe_images = st.checkbox('Remover imagens repetidas no mesmo produto', value=bool(current.get('dedupe_images')), key=f'{key_prefix}_rules_dedupe_images')
        limit_images = st.checkbox('Limitar quantidade de imagens por produto', value=bool(current.get('limit_images')), key=f'{key_prefix}_rules_limit_images')
        max_images = st.number_input('Quantidade máxima de imagens', min_value=0, max_value=50, value=int(current.get('max_images') or 6), step=1, key=f'{key_prefix}_rules_max_images')
        st.caption('O número 6 é apenas sugestão. Só limita quando o toggle estiver ligado.')

        st.markdown('#### GTIN / EAN')
        st.caption('Colunas detectadas: ' + (', '.join(gtin_cols) if gtin_cols else 'nenhuma coluna GTIN/EAN detectada agora.'))
        validate_gtin = st.checkbox('Validar GTIN/EAN e limpar inválidos', value=bool(current.get('validate_gtin')), key=f'{key_prefix}_rules_validate_gtin')

        st.markdown('#### Categoria')
        fill_category_aliases = st.checkbox('Preencher categoria vazia usando categoria da origem', value=bool(current.get('fill_category_aliases')), key=f'{key_prefix}_rules_fill_category_aliases')

        st.markdown('#### Valores padrão opcionais')
        apply_unit_default = st.checkbox('Unidade', value=bool(current.get('apply_unit_default')), key=f'{key_prefix}_rules_apply_unit_default')
        unit_value = st.text_input('Valor da Unidade', value=str(current.get('unit_value') or 'UN'), key=f'{key_prefix}_rules_unit_value')
        apply_measure_unit_default = st.checkbox('Unidade de medida', value=bool(current.get('apply_measure_unit_default')), key=f'{key_prefix}_rules_apply_measure_unit_default')
        measure_unit_value = st.text_input('Valor da Unidade de medida', value=str(current.get('measure_unit_value') or 'Centímetros'), key=f'{key_prefix}_rules_measure_unit_value')
        apply_status_default = st.checkbox('Situação / Status', value=bool(current.get('apply_status_default')), key=f'{key_prefix}_rules_apply_status_default')
        status_value = st.text_input('Valor da Situação / Status', value=str(current.get('status_value') or 'Ativo'), key=f'{key_prefix}_rules_status_value')
        apply_condition_default = st.checkbox('Condição', value=bool(current.get('apply_condition_default')), key=f'{key_prefix}_rules_apply_condition_default')
        condition_value = st.text_input('Valor da Condição', value=str(current.get('condition_value') or 'Novo'), key=f'{key_prefix}_rules_condition_value')
        apply_dimensions_default = st.checkbox('Dimensões A/L/P', value=bool(current.get('apply_dimensions_default')), key=f'{key_prefix}_rules_apply_dimensions_default')
        height_value = st.text_input('Altura padrão', value=str(current.get('height_value') or '2'), key=f'{key_prefix}_rules_height_value')
        width_value = st.text_input('Largura padrão', value=str(current.get('width_value') or '11'), key=f'{key_prefix}_rules_width_value')
        depth_value = st.text_input('Profundidade padrão', value=str(current.get('depth_value') or '16'), key=f'{key_prefix}_rules_depth_value')

        st.markdown('#### Garantias do fluxo universal')
        st.caption('Campos tratados por estas regras serão bloqueados no mapeamento manual para evitar alteração acidental.')

    config = {
        **default_smart_rules_config(),
        'enabled': True,
        'clean_text': bool(clean_text),
        'remove_empty_markers': bool(remove_empty_markers),
        'normalize_images': bool(normalize_images),
        'dedupe_images': bool(dedupe_images),
        'limit_images': bool(limit_images),
        'max_images': int(max_images),
        'validate_gtin': bool(validate_gtin),
        'fill_category_aliases': bool(fill_category_aliases),
        'apply_unit_default': bool(apply_unit_default),
        'unit_value': str(unit_value),
        'apply_measure_unit_default': bool(apply_measure_unit_default),
        'measure_unit_value': str(measure_unit_value),
        'apply_status_default': bool(apply_status_default),
        'status_value': str(status_value),
        'apply_condition_default': bool(apply_condition_default),
        'condition_value': str(condition_value),
        'apply_dimensions_default': bool(apply_dimensions_default),
        'height_value': str(height_value),
        'width_value': str(width_value),
        'depth_value': str(depth_value),
    }
    locked_fields = _build_locked_mapping_fields(source, model, config)
    _store_locked_fields(key_prefix, locked_fields)
    if locked_fields:
        st.info('Campos bloqueados no mapeamento por regras inteligentes: ' + ', '.join(locked_fields.keys()))
    st.session_state[state_key] = config
    st.session_state[previous_enabled_key] = True
    add_audit_event(
        'rules_resources_panel_rendered',
        area='UNIVERSAL',
        status='OK',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'enabled': True,
            'all_rules_opt_in': True,
            'locked_mapping_fields': locked_fields,
            'image_columns_detected': image_cols,
            'gtin_columns_detected': gtin_cols,
            'config': config,
        },
    )
    return config


__all__ = ['render_rules_resources_panel']
