from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY as UNIVERSAL_MODELO_KEY,
    CADASTRO_ORIGEM_KEY as UNIVERSAL_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY as UNIVERSAL_ORIGEM_PRICED_KEY,
    cadastro_context_ready as _cadastro_context_ready,
    cadastro_mapping_ready as universal_mapping_ready,
    clear_cadastro_outputs_if_source_changed as clear_universal_outputs_if_source_changed,
    ensure_api_direct_final_df,
    is_site_origin,
    store_cadastro_context as store_universal_context,
    valid_df,
    valid_model,
)


def universal_context_ready() -> bool:
    """Entrada pronta para seguir.

    BLINGARCH: a origem pode ser carregada antes do modelo/contrato. Por isso,
    para liberar a etapa seguinte, basta existir origem valida. O mapeamento,
    preview e download continuam dependendo de modelo/mapeamento reais.
    """
    if _cadastro_context_ready():
        return True
    return valid_df(st.session_state.get(UNIVERSAL_ORIGEM_KEY))


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
