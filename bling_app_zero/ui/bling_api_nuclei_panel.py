from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_api_flow_nuclei import api_flow_overview, api_operation_nuclei, validate_api_dataframe

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_api_nuclei_panel.py'
SOURCE_KEYS = (
    'cadastro_wizard_df_origem',
    'df_origem',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_origem_site_como_planilha',
    'df_site_bruto',
    'mapeiaai_universal_source_df',
)


def first_api_source_dataframe() -> pd.DataFrame | None:
    for key in SOURCE_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value.copy().fillna('')
    return None


def render_api_nuclei_panel(operation: object, df: pd.DataFrame | None = None, *, compact: bool = False) -> None:
    spec = api_operation_nuclei(operation)
    overview = api_flow_overview(spec.operation)
    source_df = df if isinstance(df, pd.DataFrame) and not df.empty else first_api_source_dataframe()
    result = validate_api_dataframe(source_df, spec.operation) if isinstance(source_df, pd.DataFrame) else validate_api_dataframe(pd.DataFrame(), spec.operation)
    st.session_state['bling_api_nuclei_overview'] = overview
    st.session_state['bling_api_nuclei_validation'] = result.to_dict()

    if compact:
        st.caption(f'Núcleo API: {spec.label} · mapeamento manual bloqueado · contrato automático Bling.')
    else:
        st.info(f'Fluxo API ativo: {spec.label}. A API é apenas o destino final; origem, normalização, regras, preview e envio usam o mesmo sistema.')

    with st.expander('Núcleos usados neste fluxo API', expanded=False):
        st.caption('Sequência fixa do modo API')
        st.write(' → '.join(str(item).replace('_', ' ') for item in overview['sequence']))
        st.caption('Núcleos específicos da operação')
        for item in spec.required_nuclei:
            st.markdown(f'- {str(item).replace("_", " ")}')
        for note in spec.notes:
            st.caption(f'• {note}')

    if result.ok:
        st.success('Validação estrutural da origem: obrigatórios mínimos detectados para esta operação.')
    else:
        for message in result.messages:
            st.warning(message)
    if result.warning_groups:
        st.caption('Atenções não bloqueantes: ' + ', '.join(result.warning_groups))

    add_audit_event(
        'bling_api_nuclei_panel_rendered',
        area='BLING_API',
        status='OK' if result.ok else 'ATENCAO',
        details={
            'operation': spec.operation,
            'validation': result.to_dict(),
            'manual_mapping_allowed': False,
            'same_flow_and_engines': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


__all__ = ['first_api_source_dataframe', 'render_api_nuclei_panel']
