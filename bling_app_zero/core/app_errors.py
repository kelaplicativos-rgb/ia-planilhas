from __future__ import annotations

import traceback

from bling_app_zero.core.debug import add_debug


def register_critical_error(exc: Exception) -> str:
    """Registra erro crítico e devolve traceback formatado para exibição técnica."""
    formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    add_debug(f'Falha critica: {exc}', origin='APP', level='ERRO')
    add_debug(formatted, origin='TRACEBACK', level='ERRO')
    return formatted


__all__ = ['register_critical_error']
