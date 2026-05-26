from __future__ import annotations

import threading
from typing import Callable


def inside_executor_thread() -> bool:
    """Evita chamadas indiretas ao Streamlit dentro do ThreadPoolExecutor.

    Logs visuais e callbacks do Streamlit precisam ficar fora das threads paralelas
    para evitar `missing ScriptRunContext`.
    """
    return threading.current_thread().name.startswith('ThreadPoolExecutor')


def emit(progress_callback: Callable[[dict], None] | None, payload: dict) -> None:
    if not progress_callback:
        return
    if inside_executor_thread():
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


__all__ = ['emit', 'inside_executor_thread']
