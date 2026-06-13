from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.flow_spine_output import output_diagnostics, output_is_api, output_plan
from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
    cadastro_mapping_ready,
    ensure_api_direct_final_df,
    render_row_count_blocker,
    store_expected_source_rows,
    valid_df,
    valid_model,
)
from bling_app_zero.ui.shared_mapping import render_shared_cadastro_mapping

RESPONSIBLE_FILE = 'bling_app_zero/ui/cadastro_mapping_step.py'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
CONTEXT_BLING_API = 'bling_api'
MODEL_BYTES_KEY = 'destination_model_upload_bytes'
MODEL_NAME_KEY = 'destination_model_upload_name'

MODEL_FALLBACK_KEYS = (
    CADASTRO_MODELO_KEY,
    'df_modelo_universal',
    'home_modelo_universal_df',
    'modelo_universal_df',
    'mapeiaai_final_contract_df',
    'home_modelo_cadastro_df',
    'df_modelo_cadastro',
    'modelo_cadastro_df',
    'home_modelo_estoque_df',
    'df_modelo_estoque',
    'modelo_estoque_df',
    'estoque_wizard_df_modelo',
)


class _NamedBytesIO(BytesIO):
    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


def _is_api_context() -> bool:
    try:
        return output_is_api()
    except Exception:
        return str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower() == CONTEXT_BLING_API


def _manual_mapping_required() -> bool:
    """Bling conectado pode mudar só o destino final para API, mas o contrato ainda pode exigir mapeamento.

    O bug era tratar qualquer destino api_bling como API direta e pular a tela de ligar colunas.
    No fluxo universal_mapping_csv, o usuário ainda precisa revisar/mapear os 59 campos antes do envio.
    """
    try:
        plan = output_plan()
        return bool(getattr(plan, 'needs_mapping', False))
    except Exception:
        return True


def _operation_label() -> str:
    try:
        plan = output_plan()
        return str(plan.primary_action_label or plan.operation or '').strip()
    except Exception:
        return ''


def _resolve_model_df() -> pd.DataFrame | None:
    for key in MODEL_FALLBACK_KEYS:
        value = st.session_state.get(key)
        if valid_model(value):
            model = value.copy().fillna('')
            st.session_state[CADASTRO_MODELO_KEY] = model
            st.session_state['df_modelo_universal'] = model
            st.session_state['home_modelo_universal_df'] = model
            return model

    data = st.session_state.get(MODEL_BYTES_KEY)
    name = str(st.session_state.get(MODEL_NAME_KEY) or 'modelo.csv')
    if isinstance(data, (bytes, bytearray)) and data:
        try:
            df = read_uploaded_file(_NamedBytesIO(bytes(data), name))
        except Exception:
            df = None
        if valid_model(df):
            model = df.copy().fillna('')
            st.session_state[CADASTRO_MODELO_KEY] = model
            st.session_state['df_modelo_universal'] = model
            st.session_state['home_modelo_universal_df'] = model
            return model
    return None


def _current_final_df() -> pd.DataFrame | None:
    for key in ('df_final_universal', 'df_final_cadastro'):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame):
            return value
    return None


def _render_mapping_spine_caption() -> None:
    try:
        plan = output_plan()
        st.caption(f"Fluxo ativo: {plan.contract_key} · destino: {plan.final_destination} · operação: universal")
        st.session_state['flow_spine_mapping_ready'] = True
        st.session_state['flow_spine_mapping_diagnostics'] = output_diagnostics()
    except Exception:
        pass


def _render_post_mapping_notice() -> None:
    if not cadastro_mapping_ready():
        st.info('Confirme o mapeamento para liberar a revisão, a prévia e o download.')
        return

    if _is_api_context():
        label = _operation_label() or 'enviar'
        st.success(f'Mapeamento confirmado. Continue para a prévia e {label}.')
        return

    st.success('Mapeamento confirmado. O download será liberado no final, após a revisão e a prévia.')


def _df_for_mapping(df_origem: pd.DataFrame) -> pd.DataFrame:
    df_precificado = st.session_state.get(CADASTRO_ORIGEM_PRICED_KEY)
    if isinstance(df_precificado, pd.DataFrame) and not df_precificado.empty:
        return df_precificado
    return df_origem


def render_cadastro_mapeamento_step() -> None:
    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = _resolve_model_df()
    _render_mapping_spine_caption()

    if not valid_df(df_origem):
        st.warning('Nenhuma planilha com dados carregada. Volte para Dados importados.')
        return

    store_expected_source_rows(df_origem)

    if _is_api_context() and not _manual_mapping_required():
        df_final = ensure_api_direct_final_df()
        if valid_df(df_final):
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric('Linhas carregadas', len(df_origem))
            with col_b:
                st.metric('Campos preparados', len(df_final.columns))
            st.info('Modo API direta: mapeamento manual dispensado. O fluxo seguirá com os campos preparados.')
            _render_post_mapping_notice()
            return

    if not valid_model(df_modelo):
        st.warning('Modelo para mapear ausente. Volte para Modelo para mapear.')
        return

    df_para_mapear = _df_for_mapping(df_origem)

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric('Linhas encontradas', len(df_origem))
    with col_b:
        st.metric('Colunas do modelo', len(df_modelo.columns))

    if _is_api_context() and _manual_mapping_required():
        st.info('Bling conectado: o envio aparece no final, mas o mapeamento manual continua obrigatório para ligar todos os campos do modelo.')

    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success('Preço calculado na etapa anterior. O valor calculado está disponível para o mapeamento.')

    render_shared_cadastro_mapping(df_para_mapear, df_modelo)

    df_final = _current_final_df()
    if isinstance(df_final, pd.DataFrame) and len(df_final) != len(df_origem):
        if render_row_count_blocker(df_final):
            return

    _render_post_mapping_notice()


__all__ = ['render_cadastro_mapeamento_step']
