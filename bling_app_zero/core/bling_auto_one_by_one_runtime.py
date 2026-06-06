from __future__ import annotations

from typing import Any

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_auto_one_by_one_runtime.py'
_INSTALLED = False


def install_bling_auto_one_by_one_runtime() -> bool:
    """Força envio automático linha a linha, sem pausa automática por tempo.

    O painel de envio roda dentro do ciclo do Streamlit. Para evitar que uma falha
    dentro de um lote grande encerre antes de percorrer todas as linhas, o runtime
    deixa cada ciclo processar exatamente 1 item. Se o modo automático estiver ativo,
    o próprio painel dá rerun e segue para a próxima linha até o fim.
    """
    global _INSTALLED
    if _INSTALLED:
        return False
    try:
        from bling_app_zero.ui import bling_api_batch_panel as panel

        def _one_by_one_batch_size(operation: str) -> int:
            return 1

        def _never_pause_after_slow_batch(state: dict[str, Any], elapsed: float) -> dict[str, Any]:
            try:
                add_audit_event(
                    'bling_api_batch_auto_pause_disabled_one_by_one',
                    area='BLING_ENVIO',
                    status='OK',
                    details={
                        'elapsed_seconds': round(float(elapsed or 0.0), 2),
                        'operation': str((state or {}).get('operation') or ''),
                        'reason': 'envio automatico deve continuar um por um sem exigir clique entre linhas',
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
            except Exception:
                pass
            return state

        panel._batch_size_for_operation = _one_by_one_batch_size
        panel._pause_after_slow_batch = _never_pause_after_slow_batch
        _INSTALLED = True
        add_audit_event(
            'bling_auto_one_by_one_runtime_installed',
            area='BLING_ENVIO',
            status='OK',
            details={'batch_size': 1, 'auto_pause_disabled': True, 'responsible_file': RESPONSIBLE_FILE},
        )
        return True
    except Exception as exc:
        _INSTALLED = True
        add_audit_event(
            'bling_auto_one_by_one_runtime_install_failed',
            area='BLING_ENVIO',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False


__all__ = ['install_bling_auto_one_by_one_runtime']
