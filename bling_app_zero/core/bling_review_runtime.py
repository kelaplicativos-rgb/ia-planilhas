from __future__ import annotations

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_review_runtime.py'
_INSTALLED = False


def install_review_before_api() -> bool:
    global _INSTALLED
    if _INSTALLED:
        return False
    try:
        from bling_app_zero.core import bling_intelligent_update_sender as sender
        from bling_app_zero.core.bling_product_review_engine import review_dataframe_before_bling
        from bling_app_zero.core.operation_contract import OP_ESTOQUE, normalize_operation

        original = getattr(sender, '_blingreview_original_split_rows', None)
        if original is None:
            original = sender.split_intelligent_update_rows
            setattr(sender, '_blingreview_original_split_rows', original)

        def split_rows_with_review(df, operation: str = ''):
            op = normalize_operation(operation)
            if op == OP_ESTOQUE:
                return original(df, operation)
            reviewed_df, summary = review_dataframe_before_bling(df, operation=op)
            add_audit_event(
                'bling_product_review_before_api_applied',
                area='BLING_ENVIO',
                status='OK' if summary.critical == 0 else 'AVISO',
                details={
                    'operation': op,
                    'total': summary.total,
                    'ready': summary.ready,
                    'completed': summary.completed,
                    'warning': summary.warning,
                    'critical': summary.critical,
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return reviewed_df, []

        sender.split_intelligent_update_rows = split_rows_with_review
        _INSTALLED = True
        return True
    except Exception as exc:
        add_audit_event(
            'bling_product_review_before_api_install_failed',
            area='BLING_ENVIO',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        _INSTALLED = True
        return False


__all__ = ['install_review_before_api']
