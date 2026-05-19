from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from typing import Any, Callable

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.rules_signature import rules_signature
from bling_app_zero.core.template_download_exporter import (
    build_template_download_bytes,
    can_export_from_template,
    output_name_for_template,
)
from bling_app_zero.core.validators import validate_final_df
from bling_app_zero.universal.contract_adapter import adapt_dataframe_to_model_contract, model_for_operation

PREVIEW_ROWS = 50
_PREVIEW_NESTING_KEY = '_bling_preview_nesting_level'
DESTINATION_MODEL_UPLOAD_OBJECT_KEY = 'destination_model_upload_object'
DESTINATION_MODEL_UPLOAD_NAME_KEY = 'destination_model_upload_name'

KIND_LABELS = {
    'id_produto': 'Identificador do produto',
    'codigo': 'Código/SKU',
    'gtin': 'GTIN/EAN',
    'descricao': 'Nome ou descrição',
    'deposito': 'Depósito',
    'estoque': 'Saldo/quantidade',
    'preco_custo': 'Preço de custo',
    'preco_unitario': 'Preço de venda',
    'observacao': 'Observação',
    'data': 'Data',
    'url': 'Link/URL',
    'nome_apoio': 'Nome de apoio',
    'imagem': 'Imagem',
    'marca': 'Marca',
    'categoria': 'Categoria',
    'ncm': 'NCM',
    'custom': 'Campo personalizado',
}

OPERATION_LABELS = {
    'cadastro': 'Cadastro de produtos',
    'estoque': 'Atualização de estoque',
}


class _NamedBytesIO(BytesIO):
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


@contextmanager
def _preview_context(label: str):
    level = int(st.session_state.get(_PREVIEW_NESTING_KEY, 0) or 0)
    st.session_state[_PREVIEW_NESTING_KEY] = level + 1
    opened_expander = False
    try:
        if level == 0:
            try:
                with st.expander(label, expanded=False):
                    opened_expander = True
                    yield
            except StreamlitAPIException as exc:
                if 'Expanders may not be nested' not in str(exc):
                    raise
                st.markdown(f'##### {label}')
                yield
        else:
            st.markdown(f'##### {label}')
            yield
    finally:
        current = int(st.session_state.get(_PREVIEW_NESTING_KEY, 1) or 1)
        st.session_state[_PREVIEW_NESTING_KEY] = max(0, current - 1)
        _ = opened_expander


@st.cache_data(show_spinner=False)
def _read_uploaded_file_cached(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    buffer = _NamedBytesIO(file_bytes, file_name)
    return read_uploaded_file(buffer)


def read_upload_fast(uploaded_file: Any | None) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    file_name = getattr(uploaded_file, 'name', 'arquivo')
    file_bytes = uploaded_file.getvalue()
    return _read_uploaded_file_cached(file_name, file_bytes).copy()


@st.cache_resource(show_spinner=False)
def load_cadastro_pipeline() -> Callable:
    from bling_app_zero.pipelines.cadastro_pipeline import run_pipeline

    return run_pipeline


@st.cache_resource(show_spinner=False)
def load_estoque_pipeline() -> Callable:
    from bling_app_zero.pipelines.estoque_pipeline import run_pipeline

    return run_pipeline


@st.cache_resource(show_spinner=False)
def load_site_pipeline() -> Callable:
    from bling_app_zero.pipelines.site_pipeline import run_pipeline

    return run_pipeline


@st.cache_resource(show_spinner=False)
def load_requested_columns_from_model() -> Callable:
    from bling_app_zero.flows.estoque_contract import requested_columns_from_model

    return requested_columns_from_model


def df_signature(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return 'empty'
    columns = '|'.join(map(str, df.columns))
    shape = f'{len(df)}x{len(df.columns)}'
    sample = pd.util.hash_pandas_object(df.head(200).astype(str), index=True).sum()
    return f'{shape}:{columns}:{sample}'


def _kind_label(kind: str) -> str:
    return KIND_LABELS.get(str(kind or '').strip(), 'Campo personalizado')


def _operation_label(operation: str) -> str:
    return OPERATION_LABELS.get(str(operation or '').strip().lower(), 'Planilha final')


def _operation_badge(operation: str) -> str:
    op = str(operation or '').strip().lower()
    if op == 'estoque':
        return '📦 ESTOQUE'
    if op == 'cadastro':
        return '🧾 CADASTRO'
    return '📄 PLANILHA'


def _download_label() -> str:
    return '⬇️ Baixar modelo preenchido fiel ao arquivo anexado'


def _preview_safe_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return df
    out = df.head(PREVIEW_ROWS).copy()
    for column in out.columns:
        if out[column].dtype == 'object':
            out[column] = out[column].map(lambda value: '' if pd.isna(value) else str(value))
    return out


def _render_contract_body(columns: list[str]) -> None:
    contract = build_contract(columns)
    st.caption('Serão buscados somente estes campos. Se algum dado não existir no site, ele ficará vazio.')
    st.dataframe(
        pd.DataFrame([
            {
                'Coluna solicitada': field.original,
                'Tipo detectado': _kind_label(field.kind),
                'Obrigatório': 'Sim' if field.required else 'Não',
            }
            for field in contract
        ]),
        use_container_width=True,
        height=260,
    )


def show_contract(columns: list[str]) -> None:
    if not columns:
        return
    try:
        with st.expander('Campos que serão buscados', expanded=False):
            _render_contract_body(columns)
    except StreamlitAPIException as exc:
        if 'Expanders may not be nested' not in str(exc):
            raise
        st.markdown('##### Campos que serão buscados')
        _render_contract_body(columns)


def _render_mapping_body(mapping: dict[str, str]) -> None:
    st.dataframe(
        pd.DataFrame([
            {'Campo do modelo': key, 'Origem usada': value or '(vazio)'}
            for key, value in mapping.items()
        ]).astype(str),
        use_container_width=True,
        height=260,
    )


def show_mapping(mapping: dict[str, str], operation: str | None = None) -> None:
    if not mapping:
        return
    label = 'Como os campos foram preenchidos'
    if operation:
        label = f'{_operation_badge(operation)} · Como os campos foram preenchidos'
    try:
        with st.expander(label, expanded=False):
            _render_mapping_body(mapping)
    except StreamlitAPIException as exc:
        if 'Expanders may not be nested' not in str(exc):
            raise
        st.markdown(f'##### {label}')
        _render_mapping_body(mapping)


def _preserve_flow_after_download(operation: str) -> None:
    op = str(operation or '').strip().lower()
    if op in {'cadastro', 'estoque'}:
        st.session_state['home_active_operation_v2'] = 'wizard_cadastro_estoque'
        st.session_state['home_slim_flow_operation'] = op
        try:
            st.query_params['operation_v2'] = 'wizard_cadastro_estoque'
        except Exception:
            pass


def _after_final_download(operation: str, signature: str, rules_sig: str) -> None:
    _preserve_flow_after_download(operation)
    st.session_state['final_download_cache_cleaned'] = False
    st.session_state['final_download_done'] = True
    st.session_state['final_download_operation'] = operation
    add_audit_event(
        'final_download_completed_navigation_preserved',
        area='DOWNLOAD',
        details={'operation': operation, 'signature': signature, 'rules_signature': rules_sig},
    )


def _download_dataframe_for_contract(df: pd.DataFrame, operation: str) -> tuple[pd.DataFrame, bool, list[str]]:
    model = model_for_operation(operation)
    adapted = adapt_dataframe_to_model_contract(df, model)
    applied = isinstance(model, pd.DataFrame) and len(model.columns) > 0
    model_columns = [str(column) for column in model.columns] if applied else []
    return adapted, applied, model_columns


def _get_template_upload() -> tuple[str, bytes] | None:
    uploaded = st.session_state.get(DESTINATION_MODEL_UPLOAD_OBJECT_KEY)
    if uploaded is None:
        return None
    name = str(getattr(uploaded, 'name', '') or st.session_state.get(DESTINATION_MODEL_UPLOAD_NAME_KEY) or '').strip()
    try:
        data = uploaded.getvalue()
    except Exception:
        data = None
    if not name or not data:
        return None
    return name, bytes(data)


def _build_template_download(df: pd.DataFrame) -> tuple[bytes, str, str] | None:
    template = _get_template_upload()
    if template is None:
        st.error('Modelo original ausente. Reenvie a planilha modelo para gerar o arquivo final no próprio layout anexado.')
        add_audit_event('template_download_original_missing', area='DOWNLOAD', status='BLOQUEADO')
        return None

    template_name, template_bytes = template
    if not can_export_from_template(template_name, template_bytes):
        st.error('O download final fiel exige o próprio modelo em XLSX ou XLSM. Reenvie o modelo nesse formato para preservar o arquivo exatamente como entrou.')
        add_audit_event('template_download_not_supported', area='DOWNLOAD', status='BLOQUEADO', details={'template_name': template_name})
        return None

    try:
        data = build_template_download_bytes(template_bytes=template_bytes, template_name=template_name, df=df)
        return data, output_name_for_template(template_name), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    except Exception as exc:
        add_audit_event(
            'template_download_contract_blocked',
            area='DOWNLOAD',
            status='BLOQUEADO',
            details={'template_name': template_name, 'error': str(exc)},
        )
        st.error('Contrato rígido bloqueou o download final.')
        st.warning(str(exc))
        st.caption('Nenhum outro arquivo será gerado porque o sistema só pode baixar o próprio modelo anexado preenchido.')
        return None


def download_final(df: pd.DataFrame, operation: str, key: str) -> None:
    if df is None or df.empty:
        st.warning('Ainda não há dados finais para baixar.')
        return

    operation_title = _operation_label(operation)
    st.markdown(f'##### {_operation_badge(operation)}')
    st.caption(f'Planilha final: {operation_title}. Confira a prévia acima antes de baixar.')

    if st.session_state.pop('final_download_done', False):
        st.caption('✅ Download da planilha final concluído. A etapa atual foi preservada para você continuar sem voltar para a Home.')

    download_df, contract_applied, model_columns = _download_dataframe_for_contract(df, operation)
    if contract_applied:
        st.success('Contrato aplicado: colunas e ordem seguem o modelo de destino anexado.')
        with st.expander('Contrato aplicado no download', expanded=False):
            st.caption('Colunas do arquivo final: ' + ', '.join(model_columns))
    else:
        st.error('Contrato de destino ausente. Reenvie a planilha modelo antes de baixar.')
        add_audit_event('download_contract_missing', area='DOWNLOAD', status='BLOQUEADO')
        return

    errors = validate_final_df(download_df, operation)
    if errors:
        try:
            with st.expander(f'{_operation_badge(operation)} · Conferência antes do download', expanded=True):
                for error in errors:
                    st.warning(error)
        except StreamlitAPIException as exc:
            if 'Expanders may not be nested' not in str(exc):
                raise
            st.markdown(f'##### {_operation_badge(operation)} · Conferência antes do download')
            for error in errors:
                st.warning(error)

    signature = df_signature(download_df)
    rules_sig = rules_signature()
    template_export = _build_template_download(download_df.copy())
    if template_export is None:
        return

    template_bytes, template_file_name, template_mime = template_export
    st.success('Arquivo final gerado sobre o próprio modelo anexado. Formatação, abas e estrutura do XLSX/XLSM foram preservadas.')
    st.download_button(
        _download_label(),
        data=template_bytes,
        file_name=template_file_name,
        mime=template_mime,
        use_container_width=True,
        key=f'download_template_{key}_{signature}_{rules_sig}',
        on_click=_after_final_download,
        args=(operation, signature, rules_sig),
    )


def _render_preview_body(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        st.info('Sem dados para exibir ainda.')
        return

    total_rows = len(df)
    total_cols = len(df.columns)
    safe_df = _preview_safe_df(df)
    st.dataframe(safe_df, use_container_width=True, height=360)
    if total_rows > PREVIEW_ROWS:
        st.caption(f'Mostrando {PREVIEW_ROWS} de {total_rows} linha(s). Total: {total_cols} coluna(s).')
    else:
        st.caption(f'{total_rows} linha(s) × {total_cols} coluna(s)')


def preview_df(title: str, df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        label = title
    else:
        label = f'{title} · {len(df)} linha(s) × {len(df.columns)} coluna(s)'

    with _preview_context(label):
        _render_preview_body(df)
