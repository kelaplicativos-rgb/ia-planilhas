from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.final_csv_exporter import contract_columns_from_model
from bling_app_zero.core.final_output_engine import apply_text_rules, build_final_dataframe, build_final_output, build_final_output_report
from bling_app_zero.core.template_download_exporter import (
    build_template_download_bytes,
    can_export_from_template,
    mime_for_template_output,
    output_name_for_template,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/shared_final_csv.py'
FINAL_OUTPUT_STATE_KEY = 'neutral_final_output_state_v1'
FINAL_OUTPUT_REPORT_KEY = 'neutral_final_output_report_v1'
MODEL_TEMPLATE_UPLOAD_KEYS = (
    'mapeiaai_universal_model_upload',
    'mapeiaai_shared_model_upload',
    'home_modelo_universal_upload',
)
MODEL_TEMPLATE_NAME_KEYS = (
    'mapeiaai_universal_model_file_name',
    'mapeiaai_model_template_name',
)
MODEL_TEMPLATE_BYTES_KEYS = (
    'mapeiaai_universal_model_file_bytes',
    'mapeiaai_model_template_bytes',
)
SUPPORTED_PRESERVE_SUFFIXES = {'.csv', '.xlsx', '.xlsm'}
EXCEL_LIKE_SUFFIXES = {'.xlsx', '.xlsm', '.xls', '.xlsb'}


def _render_smartcore_box(result) -> None:
    quality = result.quality
    with st.expander('Validação inteligente opcional da saída final', expanded=False):
        st.caption(f'Origem: {result.origin} · Operação: {result.operation}')
        st.metric('Qualidade da saída', f'{quality.score}/100')
        for item in quality.warnings[:8]:
            st.warning(item)


def _template_from_uploaded_widget() -> tuple[str, bytes] | None:
    for key in MODEL_TEMPLATE_UPLOAD_KEYS:
        uploaded = st.session_state.get(key)
        if uploaded is None:
            continue
        name = str(getattr(uploaded, 'name', '') or '').strip()
        try:
            data = uploaded.getvalue()
        except Exception:
            data = b''
        if name and data:
            return name, bytes(data)
    return None


def _template_from_stored_session() -> tuple[str, bytes] | None:
    for name_key in MODEL_TEMPLATE_NAME_KEYS:
        name = str(st.session_state.get(name_key) or '').strip()
        if not name:
            continue
        for bytes_key in MODEL_TEMPLATE_BYTES_KEYS:
            data = st.session_state.get(bytes_key)
            if isinstance(data, (bytes, bytearray)) and data:
                return name, bytes(data)
    return None


def _current_model_template() -> tuple[str, bytes] | None:
    return _template_from_uploaded_widget() or _template_from_stored_session()


def _suffix(file_name: str | None) -> str:
    return Path(str(file_name or '')).suffix.lower()


def _build_template_preserved_download(output: pd.DataFrame) -> tuple[bytes | None, str, str, bool, str]:
    template = _current_model_template()
    if template is None:
        return None, '', '', False, 'template_not_found'

    template_name, template_bytes = template
    suffix = _suffix(template_name)
    if suffix not in SUPPORTED_PRESERVE_SUFFIXES:
        return None, template_name, '', False, f'unsupported:{suffix or "sem_extensao"}'

    if not can_export_from_template(template_name, template_bytes):
        return None, template_name, '', False, 'cannot_export_from_template'

    file_bytes = build_template_download_bytes(template_bytes=template_bytes, template_name=template_name, df=output)
    return file_bytes, output_name_for_template(template_name), mime_for_template_output(template_name), True, 'preserved'


def _render_no_safe_download(template_name: str, template_suffix: str, preserve_status: str) -> None:
    if not template_name:
        st.error('Não encontrei o arquivo modelo original nesta sessão.')
        st.caption('Reanexe o modelo original em XLSX, XLSM ou CSV. O sistema não vai baixar CSV de fallback sem o arquivo original.')
        return
    if template_suffix in EXCEL_LIKE_SUFFIXES and template_suffix not in SUPPORTED_PRESERVE_SUFFIXES:
        st.error(f'O modelo {template_name} está em formato {template_suffix.upper()} e ainda não pode ser preservado com segurança.')
        st.caption('Use XLSX, XLSM ou CSV para download fiel ao modelo original.')
        return
    if template_suffix in EXCEL_LIKE_SUFFIXES:
        st.error(f'Não consegui gerar o arquivo preservado a partir de {template_name}.')
        st.caption('Reanexe o modelo em XLSX, XLSM ou CSV. O CSV alternativo foi desativado para não quebrar o formato original.')
        return
    st.error(f'O modelo {template_name} não está em formato aceito para preservação fiel.')
    st.caption(f'Use XLSX, XLSM ou CSV. Status técnico: {preserve_status}.')


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
    run_smart_features: bool = True,
) -> pd.DataFrame | None:
    st.markdown('### Preview final')
    st.caption('O download final usa o modelo anexado como estrutura de colunas e preenche as linhas com os dados da origem mapeada.')

    contract_columns = contract_columns_from_model(contract)
    final_result = build_final_output(
        source,
        contract,
        mapping,
        operation='universal',
        file_name=file_name,
        run_smart_features=run_smart_features,
    )
    st.session_state[FINAL_OUTPUT_STATE_KEY] = final_result.state.to_dict()
    st.session_state[FINAL_OUTPUT_REPORT_KEY] = build_final_output_report(final_result)

    if final_result.errors:
        for error in final_result.errors:
            st.error(error)
        return None

    output = final_result.output
    smartcore_result = final_result.smartcore_result
    if not isinstance(output, pd.DataFrame):
        st.error('Não foi possível montar o preview final.')
        return None

    st.success('Modelo anexado preenchido: mesmas colunas e mesma ordem do modelo, com linhas vindas da origem.')
    if smartcore_result is not None:
        _render_smartcore_box(smartcore_result)
    elif not run_smart_features:
        st.caption('Recursos inteligentes desligados: o download respeita apenas o mapeamento manual/selecionado, os valores fixos e o contrato do modelo.')
    st.dataframe(output.head(80).astype(str), use_container_width=True, height=360)
    st.caption(f'Preview: {len(output)} linha(s) da origem x {len(output.columns)} coluna(s) do modelo.')

    with st.expander('Contrato do modelo anexado', expanded=False):
        st.caption('Estas são as colunas finais, na mesma ordem do modelo anexado. As linhas do modelo não são copiadas; elas servem apenas como referência de estrutura.')
        st.dataframe(pd.DataFrame({'Colunas do modelo': contract_columns}), use_container_width=True, hide_index=True)

    st.markdown('### Planilha final preenchida')
    preserved_bytes = None
    preserved_name = ''
    preserved_mime = ''
    preserved = False
    preserve_status = 'template_not_found'
    try:
        preserved_bytes, preserved_name, preserved_mime, preserved, preserve_status = _build_template_preserved_download(output)
    except Exception as exc:
        preserve_status = f'error:{str(exc)[:180]}'
        st.error(f'Download fiel ao modelo original falhou: {exc}')

    template = _current_model_template()
    template_name = template[0] if template else ''
    template_suffix = _suffix(template_name)

    if preserved and preserved_bytes is not None:
        st.success(f'Arquivo final preservado no formato original do modelo: {preserved_name}')
        st.download_button(
            'Baixar modelo original preenchido',
            data=preserved_bytes,
            file_name=preserved_name,
            mime=preserved_mime,
            use_container_width=True,
            key=f'{key_prefix}_download_template_preserved',
            help='Download gerado dentro do arquivo modelo original, preservando formato, abas e estrutura sempre que possível.',
        )
    else:
        _render_no_safe_download(template_name, template_suffix, preserve_status)
    add_audit_event(
        'shared_final_csv_rendered',
        area='FINAL_CSV',
        status='OK',
        details={
            'rows': int(len(output)),
            'columns': int(len(output.columns)),
            'contract_columns': contract_columns,
            'contract_identity': True,
            'model_as_column_contract_only': True,
            'source_rows_as_output_rows': True,
            'template_preserved_download': bool(preserved),
            'template_preserve_status': preserve_status,
            'template_name': template_name,
            'csv_fallback_blocked': True,
            'smartcore_score': int(final_result.state.result.smartcore_score),
            'run_smart_features': bool(run_smart_features),
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
