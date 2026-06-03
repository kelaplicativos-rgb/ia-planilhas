from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.final_csv_exporter import contract_columns_from_model
from bling_app_zero.core.final_output_engine import apply_text_rules, build_final_dataframe, build_final_output, build_final_output_report

RESPONSIBLE_FILE = 'bling_app_zero/ui/shared_final_csv.py'
FINAL_OUTPUT_STATE_KEY = 'neutral_final_output_state_v1'
FINAL_OUTPUT_REPORT_KEY = 'neutral_final_output_report_v1'


def _render_smartcore_box(result) -> None:
    quality = result.quality
    with st.expander('BLINGSMARTCORE · validação inteligente da saída final', expanded=False):
        st.caption(f'Origem: {result.origin} · Operação: {result.operation}')
        st.metric('Qualidade da saída', f'{quality.score}/100')
        for item in quality.warnings[:8]:
            st.warning(item)


def apply_shared_text_rules(output: pd.DataFrame) -> pd.DataFrame:
    return apply_text_rules(output)


def build_shared_final_dataframe(source: pd.DataFrame, contract: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    return build_final_dataframe(source, contract, mapping)


def render_shared_final_csv(
    source: pd.DataFrame,
    contract: pd.DataFrame,
    mapping: dict[str, str],
    *,
    key_prefix: str = 'mapeiaai_shared_final',
    file_name: str = 'mapeiaai_planilha_final_mapeada.csv',
) -> pd.DataFrame | None:
    st.markdown('### Preview final')

    contract_columns = contract_columns_from_model(contract)
    final_result = build_final_output(
        source,
        contract,
        mapping,
        operation='universal',
        file_name=file_name,
    )
    st.session_state[FINAL_OUTPUT_STATE_KEY] = final_result.state.to_dict()
    st.session_state[FINAL_OUTPUT_REPORT_KEY] = build_final_output_report(final_result)

    if final_result.errors:
        for error in final_result.errors:
            st.error(error)
        return None

    output = final_result.output
    csv_bytes = final_result.csv_bytes
    smartcore_result = final_result.smartcore_result
    if not isinstance(output, pd.DataFrame):
        st.error('Não foi possível montar o preview final.')
        return None

    st.success('Planilha final fiel ao modelo anexado: mesmas colunas, mesma ordem e sem extras.')
    if smartcore_result is not None:
        _render_smartcore_box(smartcore_result)
    st.dataframe(output.head(80).astype(str), use_container_width=True, height=360)
    st.caption(f'Preview: {len(output)} linha(s) x {len(output.columns)} coluna(s).')

    with st.expander('Contrato do download final', expanded=False):
        st.caption('Estas são as colunas que serão usadas no CSV final, na mesma ordem do modelo anexado.')
        st.dataframe(pd.DataFrame({'Colunas do modelo': contract_columns}), use_container_width=True, hide_index=True)

    st.markdown('### Planilha final')
    st.download_button(
        'Baixar planilha final mapeada',
        data=csv_bytes,
        file_name=file_name,
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'{key_prefix}_download',
        help='Download gerado pelo contrato do modelo anexado: mesmas colunas e mesma ordem.',
    )
    add_audit_event(
        'shared_final_csv_rendered',
        area='FINAL_CSV',
        status='OK',
        details={
            'rows': int(len(output)),
            'columns': int(len(output.columns)),
            'contract_columns': contract_columns,
            'contract_identity': True,
            'blingsmartcore_score': int(final_result.state.result.smartcore_score),
            'neutral_final_output_state': True,
            'csv_size_bytes': int(final_result.state.result.csv_size_bytes),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return output


__all__ = [
    'apply_shared_text_rules',
    'build_shared_final_dataframe',
    'render_shared_final_csv',
]
