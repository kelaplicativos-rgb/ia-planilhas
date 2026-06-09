from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_safety_guard import install_preventive_operation_guard

RESPONSIBLE_FILE = 'bling_app_zero/ui/preventive_bootstrap.py'


def install_preventive_bootstrap() -> None:
    """Executa proteções leves no boot sem derrubar a UI.

    Este bootstrap é intencionalmente defensivo: qualquer falha nele vira log de
    aviso e o app principal continua abrindo. Ele existe para evitar que uma
    operação presa deixe o usuário sem saída entre reruns do Streamlit.
    """
    try:
        decision = install_preventive_operation_guard(st.session_state)
        if not decision.ok:
            st.warning(decision.message)
            add_audit_event(
                'preventive_bootstrap_user_notice_rendered',
                area='APP',
                step='startup',
                status='AVISO',
                details={
                    'reason': decision.reason,
                    'details': decision.details or {},
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
    except Exception as exc:
        add_audit_event(
            'preventive_bootstrap_failed_non_blocking',
            area='APP',
            step='startup',
            status='AVISO',
            details={'error': str(exc)[:300], 'responsible_file': RESPONSIBLE_FILE},
        )


__all__ = ['install_preventive_bootstrap']
