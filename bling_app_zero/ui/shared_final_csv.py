from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_text_rules import clean_title_to_limit, is_description_column, is_title_column
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.final_csv_exporter import final_csv_bytes
from bling_app_zero.universal.output_builder import build_universal_output, empty_universal_output
from bling_app_zero.universal.universal_contract import build_universal_contract, validate_universal_output


def apply_shared_text_rules(output: pd.DataFrame) -> pd.DataFrame:
    out = output.copy().fillna('')
    for column in out.columns:
        if is_title_column(column):
            out[column] = out[column].map(clean_title_to_limit)
        elif is_description_column(column):
            out[column] = out[column].map(lambda value: re.sub(r'\s+', ' ', str(value or '').strip()))
    return out


def build_shared_final_dataframe(source: pd.DataFrame, contract: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    if not isinstance(source, pd.DataFrame) or source.empty:
        output = empty_universal_output(contract, rows=0)
    else:
        output = build_universal_output(source, contract, mapping)
    return apply_shared_text_rules(output)


def render_shared_final_csv(
    source: pd.DataFrame,
    contract: pd.DataFrame,
    mapping: dict[str, str],
    *,
    key_prefix: str = 'mapeiaai_shared_final',
    file_name: str = 'mapeiaai_planilha_final_mapeada.csv',
) -> pd.DataFrame | None:
    st.markdown('### Preview final')
    contract_obj = build_universal_contract(contract)
    output = build_shared_final_dataframe(source, contract, mapping)
    errors = validate_universal_output(output, contract_obj)
    if errors:
        for error in errors:
            st.error(error)
        return None

    st.success('Planilha final fiel ao contrato anexado: mesmas colunas, mesma ordem, sem extras.')
    st.dataframe(output.head(80).astype(str), use_container_width=True, height=360)
    st.caption(f'Preview: {len(output)} linha(s) × {len(output.columns)} coluna(s).')

    st.markdown('### Planilha final')
    st.download_button(
        '⬇️ Baixar planilha final mapeada',
        data=final_csv_bytes(output, operation='universal', run_download_features=True),
        file_name=file_name,
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'{key_prefix}_download',
    )
    add_audit_event(
        'shared_final_csv_rendered',
        area='FINAL_CSV',
        details={'rows': int(len(output)), 'columns': int(len(output.columns)), 'responsible_file': 'bling_app_zero/ui/shared_final_csv.py'},
    )
    return output


__all__ = [
    'apply_shared_text_rules',
    'build_shared_final_dataframe',
    'render_shared_final_csv',
]
