from __future__ import annotations

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_contract import OP_CADASTRO, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/verified_sender_runtime.py'
_INSTALLED = False


def install_verified_sender_runtime() -> bool:
    global _INSTALLED
    if _INSTALLED:
        return False
    try:
        from bling_app_zero.core import bling_intelligent_update_sender as sender
        from bling_app_zero.core.verified_api_sender_guarded import send_verified_products

        original = getattr(sender, '_verified_original_send_dataframe_to_bling_intelligent', None)
        if original is None:
            original = sender.send_dataframe_to_bling_intelligent
            setattr(sender, '_verified_original_send_dataframe_to_bling_intelligent', original)

        def guarded_send_dataframe_to_bling_intelligent(df, operation, *, limit=None, progress_callback=None):
            op = normalize_operation(operation)
            if op == OP_CADASTRO:
                add_audit_event(
                    'verified_sender_runtime_route_applied',
                    area='BLING_ENVIO',
                    status='OK',
                    details={
                        'operation': op,
                        'mode': 'produto_por_produto_com_check',
                        'sender_guard': 'verified_api_sender_guarded.py',
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
                return send_verified_products(df, limit=limit, progress_callback=progress_callback)
            return original(df, operation, limit=limit, progress_callback=progress_callback)

        sender.send_dataframe_to_bling_intelligent = guarded_send_dataframe_to_bling_intelligent

        try:
            from bling_app_zero.ui import bling_api_batch_panel
            setattr(bling_api_batch_panel, 'send_dataframe_to_bling_intelligent', guarded_send_dataframe_to_bling_intelligent)
            panel_patched = True
        except Exception as exc:
            panel_patched = False
            add_audit_event(
                'verified_sender_runtime_panel_patch_failed',
                area='BLING_ENVIO',
                status='AVISO',
                details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
            )

        _INSTALLED = True
        add_audit_event(
            'verified_sender_runtime_installed',
            area='BLING_ENVIO',
            status='OK',
            details={
                'panel_reference_patched': panel_patched,
                'sender_guard': 'verified_api_sender_guarded.py',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return True
    except Exception as exc:
        _INSTALLED = True
        add_audit_event('verified_sender_runtime_install_failed', area='BLING_ENVIO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False


__all__ = ['install_verified_sender_runtime']
