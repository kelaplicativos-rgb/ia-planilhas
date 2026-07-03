from __future__ import annotations

from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_locked_fields_runtime.py'


def _audit(event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='MAPEAMENTO', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def install() -> bool:
    """Backward-compatible entrypoint for older imports.

    The old implementation made smart-rule fields read-only. Smart rules are now
    editable gold suggestions, so this module only delegates to the visibility
    runtime that installs the new behavior.
    """
    try:
        from bling_app_zero.ui.mapping_visibility_runtime import install_mapping_visibility_runtime
    except Exception as exc:
        _audit('mapping_locked_fields_compat_import_failed', status='AVISO', details={'error': str(exc)[:220]})
        return False

    installed = bool(install_mapping_visibility_runtime())
    _audit(
        'mapping_locked_fields_compat_delegated_to_gold_runtime',
        details={
            'read_only': False,
            'user_can_edit_locked_fields': True,
            'gold_smart_rule_options': True,
            'installed_now': installed,
        },
    )
    return installed


__all__ = ['install']