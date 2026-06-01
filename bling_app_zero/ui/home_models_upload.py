from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
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
    set_step_without_rerun(STEP_ORIGEM)
    set_scroll_target(STEP_ORIGEM)
    add_audit_event(
        'home_model_uploaded_auto_forward_to_origin',
        area='MODELO',
        step=STEP_ORIGEM,
        status='OK',
        details={
            'signature': signature,
            'previous_signature': previous_signature,
            'target_step': STEP_ORIGEM,
            'scroll_target': STEP_ORIGEM,
            'cadastro': df_log_summary(cadastro_model),
            'estoque': df_log_summary(estoque_model),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    safe_rerun('home_model_uploaded_auto_forward', target_step=STEP_ORIGEM)


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
