from __future__ import annotations

import traceback

from bling_app_zero.core.debug import add_debug


def register_critical_error(exc: Exception) -> str:
    """Registra erro crítico e devolve traceback formatado para exibição técnica."""
    formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    add_debug(f'Falha critica: {exc}', origin='APP', level='ERRO')
    add_debug(formatted, origin='TRACEBACK', level='ERRO')
    try:
        from bling_app_zero.core.openai_error_monitor import record_exception_for_openai

        record_exception_for_openai(exc, area='APP')
    except Exception as monitor_exc:
        add_debug(f'Falha ao registrar erro no diagnostico IA: {monitor_exc}', origin='DIAGNOSTICO_IA', level='AVISO')
    return formatted


__all__ = ['register_critical_error']
