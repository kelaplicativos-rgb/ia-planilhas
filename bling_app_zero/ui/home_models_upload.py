from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.features_runtime.router import active_contract, feature_needs_pricing
from bling_app_zero.ui.home_models_state import (
    DESTINATION_MODEL_UPLOAD_BYTES_KEY,
    DESTINATION_MODEL_UPLOAD_NAME_KEY,
    DESTINATION_MODEL_UPLOAD_OBJECT_KEY,
    MODEL_UPLOAD_AUTOFORWARDED_KEY,
    MODEL_UPLOAD_SIGNATURE_KEY,
    STEP_ORIGEM,
    WIZARD_STEP_KEY,
    df_log_summary,
    models_signature,
)
from bling_app_zero.ui.home_wizard_rerun import safe_rerun, set_step_without_rerun
from bling_app_zero.ui.home_wizard_scroll import set_scroll_target

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_models_upload.py'
STEP_ENTRADA = 'entrada'
STEP_MAPEAMENTO = 'mapeamento'
STEP_PRECIFICACAO = 'precificacao'
STEP_DOWNLOAD = 'download'


def _origin_data_ready() -> bool:
    """Retorna True quando a origem já foi carregada antes do modelo.

    Este helper evita import circular com home_wizard.py. O caso principal é:
    usuário escolhe Site, busca produtos, depois anexa a planilha modelo.
    Antes o upload do modelo sempre mandava para Origem. Agora, se a origem já
    está pronta, o próximo passo é Mapeamento/Precificação.
    """
    try:
        from bling_app_zero.ui.universal_wizard_state import universal_context_ready

        if bool(universal_context_ready()):
            return True
    except Exception:
        pass

    for key in (
        'df_site_bruto',
        'df_site_bruto_universal',
        'df_site_bruto_cadastro',
        'df_site_bruto_estoque',
        'df_site_bruto_atualizacao_preco',
        'df_origem_cadastro',
        'df_origem_estoque',
        'df_origem_universal',
        'df_origem_site_como_planilha_universal',
        'df_origem_site_como_planilha_cadastro',
        'df_origem_site_como_planilha_estoque',
        'df_origem_site_como_planilha_atualizacao_preco',
    ):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and len(value.columns) > 0:
            return True

    return bool(st.session_state.get('site_capture_result_ready')) and int(st.session_state.get('site_capture_rows') or 0) > 0


def _target_after_model_upload() -> tuple[str, str]:
    if not _origin_data_ready():
        return STEP_ORIGEM, 'origin_missing_after_model_upload'

    contract = active_contract()
    if contract.is_api:
        return STEP_DOWNLOAD, 'api_origin_ready_after_model_upload'
    if feature_needs_pricing():
        return STEP_PRECIFICACAO, 'pricing_required_origin_ready_after_model_upload'
    return STEP_MAPEAMENTO, 'mapping_ready_after_model_upload'


def auto_forward_after_first_model_upload(cadastro_model: pd.DataFrame | None, estoque_model: pd.DataFrame | None) -> None:
    signature = models_signature(cadastro_model, estoque_model)
    if signature == 'cadastro=empty|estoque=empty':
        add_audit_event(
            'home_model_uploaded_empty_no_autoforward',
            area='MODELO',
            step=st.session_state.get(WIZARD_STEP_KEY),
            status='BLOQUEADO',
            details={
                'signature': signature,
                'cadastro': df_log_summary(cadastro_model),
                'estoque': df_log_summary(estoque_model),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return

    st.session_state[MODEL_UPLOAD_SIGNATURE_KEY] = signature
    previous_signature = st.session_state.get(MODEL_UPLOAD_AUTOFORWARDED_KEY)
    if previous_signature == signature:
        add_audit_event(
            'home_model_autoforward_already_done',
            area='MODELO',
            step=st.session_state.get(WIZARD_STEP_KEY),
            status='OK',
            details={
                'signature': signature,
                'current_step': st.session_state.get(WIZARD_STEP_KEY),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return

    st.session_state[MODEL_UPLOAD_AUTOFORWARDED_KEY] = signature
    target_step, target_reason = _target_after_model_upload()
    set_step_without_rerun(target_step)
    set_scroll_target(target_step)
    add_audit_event(
        'home_model_uploaded_auto_forward_resolved',
        area='MODELO',
        step=target_step,
        status='OK',
        details={
            'signature': signature,
            'previous_signature': previous_signature,
            'target_step': target_step,
            'target_reason': target_reason,
            'origin_data_ready': _origin_data_ready(),
            'scroll_target': target_step,
            'cadastro': df_log_summary(cadastro_model),
            'estoque': df_log_summary(estoque_model),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    safe_rerun('home_model_uploaded_auto_forward_resolved', target_step=target_step)


def remember_original_model_upload(upload: object) -> None:
    model_file = getattr(upload, 'model_file', None) or getattr(upload, 'cadastro_model_file', None) or getattr(upload, 'estoque_model_file', None)
    if model_file is None:
        return

    file_name = str(getattr(model_file, 'name', 'modelo'))
    file_bytes = b''
    try:
        raw = model_file.getvalue()
        file_bytes = bytes(raw) if raw is not None else b''
    except Exception:
        file_bytes = b''

    st.session_state[DESTINATION_MODEL_UPLOAD_OBJECT_KEY] = model_file
    st.session_state[DESTINATION_MODEL_UPLOAD_NAME_KEY] = file_name
    if file_bytes:
        st.session_state[DESTINATION_MODEL_UPLOAD_BYTES_KEY] = file_bytes

    add_audit_event(
        'destination_model_upload_object_saved',
        area='MODELO',
        status='OK',
        details={
            'name': file_name,
            'bytes_saved': bool(file_bytes),
            'bytes_len': len(file_bytes),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


__all__ = ['auto_forward_after_first_model_upload', 'remember_original_model_upload']
