from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.universal_smart_rules import default_smart_rules_config, normalize_smart_rules_config

RESPONSIBLE_FILE = 'bling_app_zero/ui/shared_rules_resources.py'
STATE_KEY_SUFFIX = 'rules_resources_config'


def _detect_columns(df: pd.DataFrame, terms: tuple[str, ...]) -> list[str]:
    if not isinstance(df, pd.DataFrame):
        return []
    out: list[str] = []
    for column in df.columns:
        name = str(column or '').casefold()
        if any(term in name for term in terms):
            out.append(str(column))
    return out


def render_rules_resources_panel(
    source: pd.DataFrame,
    model: pd.DataFrame,
    *,
    enabled: bool,
    key_prefix: str = 'mapeiaai_universal',
) -> dict[str, Any]:
    state_key = f'{key_prefix}_{STATE_KEY_SUFFIX}'
    current = normalize_smart_rules_config(st.session_state.get(state_key), enabled=enabled)
    if not enabled:
        current['enabled'] = False
        st.session_state[state_key] = current
        return current

    st.markdown('### Regras e recursos inteligentes')
    st.caption('Configure opcionais antes do preview/download. Tudo nasce desligado e nada muda as colunas do modelo.')

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
        st.caption('Campos não mapeados continuam vazios, exceto toggles ligados. A ordem e os nomes das colunas do modelo são preservados.')

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
    st.session_state[state_key] = config
    add_audit_event(
        'rules_resources_panel_rendered',
        area='UNIVERSAL',
        status='OK',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'enabled': True,
            'all_rules_opt_in': True,
            'image_columns_detected': image_cols,
            'gtin_columns_detected': gtin_cols,
            'config': config,
        },
    )
    return config


__all__ = ['render_rules_resources_panel']
