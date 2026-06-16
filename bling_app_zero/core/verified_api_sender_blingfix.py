from __future__ import annotations

from bling_app_zero.core.verified_api_sender import send_verified_products as _original_send_verified_products
from bling_app_zero.core.bling_direct_sender import DirectSendResult
from bling_app_zero.core.bling_pre_send_defaults import apply_dataframe_send_defaults
from bling_app_zero.core.blingfix_verified_runtime_patch import apply_blingfix_to_verified_module as _apply_payload_guard
from bling_app_zero.core.verified_error_context import enrich_verified_errors

RESPONSIBLE_FILE = 'bling_app_zero/core/verified_api_sender_guarded.py'


def _with_enriched_errors(result: DirectSendResult, df) -> DirectSendResult:
    enriched = enrich_verified_errors(tuple(result.errors or ()), df)
    if enriched == tuple(result.errors or ()):  # nada para enriquecer
        return result
    return DirectSendResult(
        attempted=result.attempted,
        sent=result.sent,
        failed=result.failed,
        skipped=result.skipped,
        errors=enriched,
        not_found_indices=tuple(result.not_found_indices or ()),
    )


def send_verified_products(df, *, limit=None, progress_callback=None):
    from bling_app_zero.core import verified_api_sender

    _apply_payload_guard(verified_api_sender)
    fixed_df = apply_dataframe_send_defaults(df)
    result = _original_send_verified_products(fixed_df, limit=limit, progress_callback=progress_callback)
    return _with_enriched_errors(result, fixed_df)


__all__ = ['RESPONSIBLE_FILE', 'send_verified_products']
