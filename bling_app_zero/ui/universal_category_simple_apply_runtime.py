from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_intelligence import apply_category_suggestions, classify_dataframe
from bling_app_zero.ui.home_wizard_rerun import safe_rerun

RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_category_simple_apply_runtime.py'
PATCH_ATTR = '_mapeiaai_universal_category_simple_apply_runtime_v1'
CATEGORY_CONFIDENCE_MIN = 0.80
CATEGORY_APPLIED_DF_KEY = 'mapeiaai_universal_category_applied_df_v1'
CATEGORY_APPLIED_SIGNATURE_KEY = 'mapeiaai_universal_category_applied_signature_v1'
CATEGORY_APPLIED_STATS_KEY = 'mapeiaai_universal_category_applied_stats_v1'
CATEGORY_APPLY_BUTTON_KEY = 'mapeiaai_universal_category_apply_suggested_v1'


def _valid_df(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and not value.empty and len(value.columns) > 0


def _audit(event: str, **details: object) -> None:
    add_audit_event(event, area='UNIVERSAL', status='OK', details={'responsible_file': RESPONSIBLE_FILE, **details})


def _category_signature(flow: Any, df: pd.DataFrame) -> str:
    try:
        base = flow._df_signature(df)
    except Exception:
        base = f'{len(df)}x{len(df.columns)}'
    return f'{base}:category_confidence={CATEGORY_CONFIDENCE_MIN}'


def _clear_category_state() -> None:
    for key in (CATEGORY_APPLIED_DF_KEY, CATEGORY_APPLIED_SIGNATURE_KEY, CATEGORY_APPLIED_STATS_KEY):
        st.session_state.pop(key, None)


def _category_already_applied(flow: Any, base: pd.DataFrame) -> bool:
    if not _valid_df(base):
        return False
    stored = st.session_state.get(CATEGORY_APPLIED_DF_KEY)
    if not _valid_df(stored):
        return False
    if len(stored) != len(base):
        return False
    return str(st.session_state.get(CATEGORY_APPLIED_SIGNATURE_KEY) or '') == _category_signature(flow, base)


def _stored_category_df(flow: Any, base: pd.DataFrame) -> pd.DataFrame | None:
    if not _category_already_applied(flow, base):
        return None
    stored = st.session_state.get(CATEGORY_APPLIED_DF_KEY)
    return stored.copy().fillna('') if isinstance(stored, pd.DataFrame) else None


def install_universal_category_simple_apply_runtime() -> bool:
    try:
        from bling_app_zero.ui import universal_flow as flow
    except Exception as exc:
        add_audit_event('universal_category_simple_apply_runtime_import_failed', area='UNIVERSAL', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False

    if getattr(flow, PATCH_ATTR, False):
        return False

    original_clear_after_source = getattr(flow, '_clear_after_source')
    original_clear_after_model = getattr(flow, '_clear_after_model')

    def patched_clear_after_source() -> None:
        _clear_category_state()
        original_clear_after_source()

    def patched_clear_after_model() -> None:
        _clear_category_state()
        original_clear_after_model()

    def render_category_config_simple() -> tuple[bool, float]:
        st.markdown('### Categorização')
        enabled = st.toggle('Categorização automática', value=bool(st.session_state.get(flow.UNIVERSAL_CATEGORY_ENABLED_KEY)), key='mapeiaai_universal_toggle_category')
        st.session_state[flow.UNIVERSAL_CATEGORY_ENABLED_KEY] = bool(enabled)
        if not enabled:
            _clear_category_state()
            st.caption('Desligado. As categorias serão mantidas como vieram da origem/mapeamento.')
            return False, CATEGORY_CONFIDENCE_MIN
        st.caption('Ligado. O sistema vai sugerir as categorias e só grava na planilha quando você clicar no botão abaixo.')
        return True, CATEGORY_CONFIDENCE_MIN

    def apply_category_group_simple(source: pd.DataFrame, confidence_min: float = CATEGORY_CONFIDENCE_MIN) -> pd.DataFrame:
        if not _valid_df(source):
            return source

        base = source.copy().fillna('')
        stored = _stored_category_df(flow, base)
        if isinstance(stored, pd.DataFrame):
            stats = st.session_state.get(CATEGORY_APPLIED_STATS_KEY)
            applied = int((stats or {}).get('applied', 0)) if isinstance(stats, Mapping) else 0
            st.success(f'Categorização sugerida aplicada na planilha: {len(stored)} produto(s), {applied} categoria(s) preenchida(s)/corrigida(s).')
            return stored

        try:
            analyzed, stats = classify_dataframe(base)
            output, applied = apply_category_suggestions(
                analyzed,
                confidence_min=CATEGORY_CONFIDENCE_MIN,
                keep_helper_columns=False,
                fallback_unclassified=False,
            )
        except Exception as exc:
            st.warning(f'Categorização não aplicada: {exc}')
            _audit('universal_category_simple_apply_failed', error=str(exc)[:220])
            return base

        total = int(stats.get('total', len(base)) or len(base))
        revisar = int(stats.get('revisar', 0) or 0)
        st.success(f'Categorização pronta: {total} produto(s), {applied} categoria(s) sugerida(s) para aplicar.')
        if revisar:
            st.info(f'{revisar} produto(s) ficaram sem sugestão segura e serão mantidos como estão.')

        if st.button('✅ Aplicar categorização sugerida na planilha', use_container_width=True, key=CATEGORY_APPLY_BUTTON_KEY):
            st.session_state[CATEGORY_APPLIED_DF_KEY] = output.copy().fillna('')
            st.session_state[CATEGORY_APPLIED_SIGNATURE_KEY] = _category_signature(flow, base)
            st.session_state[CATEGORY_APPLIED_STATS_KEY] = {**dict(stats or {}), 'applied': int(applied)}
            _audit(
                'universal_category_suggested_applied_to_sheet',
                rows=int(len(output)),
                columns=int(len(output.columns)),
                applied_count=int(applied),
                confidence_min=CATEGORY_CONFIDENCE_MIN,
                slider_removed=True,
                manual_grid_removed=True,
                only_apply_button=True,
            )
            st.success('Categorização aplicada na planilha. Continue para o mapeamento.')
            safe_rerun('universal_category_suggested_applied_to_sheet')
            return output

        st.info('Clique em **Aplicar categorização sugerida na planilha** para gravar as categorias antes de avançar.')
        return base

    def render_options_step_simple(model: pd.DataFrame, source: pd.DataFrame) -> None:
        st.markdown('### 3. Opcionais')
        st.caption('Aplique preço, categorização automática e regras antes do mapeamento.')
        processed = source.copy().fillna('')
        processed, price_enabled = flow._render_price_group(processed, model)
        category_enabled, category_confidence = flow._render_category_config()
        category_base = processed.copy().fillna('')
        category_ready = True
        if category_enabled:
            processed = flow._apply_category_group(category_base, category_confidence)
            category_ready = _category_already_applied(flow, category_base)
        rules_config, rules_enabled = flow._render_rules_group(processed, model)
        if category_enabled and not category_ready:
            st.warning('Para avançar, clique primeiro em **Aplicar categorização sugerida na planilha**.')
        if st.button('Aplicar opcionais e ir para mapeamento ➡️', use_container_width=True, key='mapeiaai_universal_apply_options', disabled=bool(category_enabled and not category_ready)):
            flow._store_df(flow.UNIVERSAL_PROCESSED_KEY, processed)
            st.session_state[flow.UNIVERSAL_PRICE_ENABLED_KEY] = bool(price_enabled)
            st.session_state[flow.UNIVERSAL_CATEGORY_ENABLED_KEY] = bool(category_enabled)
            st.session_state[flow.UNIVERSAL_RULES_ENABLED_KEY] = bool(rules_enabled)
            st.session_state[flow.UNIVERSAL_RULES_CONFIG_KEY] = dict(rules_config or {})
            flow._clear_after_options()
            flow._audit(
                'universal_options_applied_before_mapping',
                rows=int(len(processed)),
                columns=int(len(processed.columns)),
                price_enabled=price_enabled,
                category_enabled=category_enabled,
                rules_enabled=rules_enabled,
                category_simple_apply_button=True,
                manual_category_grid_removed=True,
            )
            flow._set_step(flow.STEP_MAPPING, 'options_applied')

    flow._clear_after_source = patched_clear_after_source
    flow._clear_after_model = patched_clear_after_model
    flow._render_category_config = render_category_config_simple
    flow._apply_category_group = apply_category_group_simple
    flow._render_options_step = render_options_step_simple
    setattr(flow, PATCH_ATTR, True)

    add_audit_event(
        'universal_category_simple_apply_runtime_installed',
        area='UNIVERSAL',
        status='OK',
        details={
            'slider_removed': True,
            'manual_grid_removed': True,
            'button_label': 'Aplicar categorização sugerida na planilha',
            'confidence_min_fixed': CATEGORY_CONFIDENCE_MIN,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['install_universal_category_simple_apply_runtime']
