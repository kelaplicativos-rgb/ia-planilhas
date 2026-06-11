from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY as UNIVERSAL_MODELO_KEY,
    CADASTRO_ORIGEM_KEY as UNIVERSAL_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY as UNIVERSAL_ORIGEM_PRICED_KEY,
    cadastro_context_ready as _cadastro_context_ready,
    cadastro_mapping_ready as _cadastro_mapping_ready,
    clear_cadastro_outputs_if_source_changed as clear_universal_outputs_if_source_changed,
    ensure_api_direct_final_df,
    is_site_origin,
    store_cadastro_context as store_universal_context,
    valid_df,
    valid_model,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/universal_wizard_state.py'

ORIGIN_FALLBACK_KEYS = (
    UNIVERSAL_ORIGEM_KEY,
    UNIVERSAL_ORIGEM_PRICED_KEY,
    'df_origem',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_origem_site',
    'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_universal',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha_atualizacao_preco',
    'df_origem_cadastro',
    'df_origem_estoque',
    'df_origem_universal',
    'df_site_bruto',
    'df_site_bruto_universal',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_atualizacao_preco',
    'estoque_wizard_df_origem_site',
)


def _force_universal_state() -> None:
    st.session_state['destination_model_contract_type'] = 'universal'
    st.session_state['destination_model_contract_label'] = 'Modelo para mapear'
    st.session_state['home_slim_flow_operation'] = 'universal'
    st.session_state['home_detected_operation'] = 'universal'
    st.session_state['operacao_final'] = 'universal'
    st.session_state['tipo_operacao_final'] = 'universal'
    st.session_state['flow_spine_operation'] = 'universal'
    st.session_state['active_feature_operation'] = 'universal'


def _copy_valid_df(value) -> pd.DataFrame | None:
    if isinstance(value, pd.DataFrame) and not value.empty and len(value.columns) > 0:
        return value.copy().fillna('')
    return None


def _origin_fallback_df() -> tuple[pd.DataFrame | None, str]:
    _force_universal_state()
    for key in ORIGIN_FALLBACK_KEYS:
        df = _copy_valid_df(st.session_state.get(key))
        if df is not None:
            if key != UNIVERSAL_ORIGEM_KEY:
                st.session_state[UNIVERSAL_ORIGEM_KEY] = df.copy()
            return df, key
    return None, ''


def universal_context_ready() -> bool:
    _force_universal_state()
    if _cadastro_context_ready():
        return True
    if valid_df(st.session_state.get(UNIVERSAL_ORIGEM_KEY)):
        return True
    df, source_key = _origin_fallback_df()
    if df is not None:
        try:
            from bling_app_zero.core.audit import add_audit_event

            add_audit_event(
                'universal_origin_resolved_from_fallback',
                area='UNIVERSAL',
                step=st.session_state.get('bling_wizard_step'),
                status='OK',
                details={
                    'source_key': source_key,
                    'rows': int(len(df)),
                    'columns': [str(column) for column in list(df.columns)[:60]],
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
        except Exception:
            pass
        return True
    return False


def universal_mapping_ready() -> bool:
    _force_universal_state()
    if _cadastro_mapping_ready():
        return True
    try:
        from bling_app_zero.ui.estoque_wizard_state import estoque_output_ready

        if bool(estoque_output_ready()):
            return True
    except Exception:
        pass
    return False


__all__ = [
    'UNIVERSAL_MODELO_KEY',
    'UNIVERSAL_ORIGEM_KEY',
    'UNIVERSAL_ORIGEM_PRICED_KEY',
    'clear_universal_outputs_if_source_changed',
    'ensure_api_direct_final_df',
    'is_site_origin',
    'store_universal_context',
    'universal_context_ready',
    'universal_mapping_ready',
    'valid_df',
    'valid_model',
]
