from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from bling_app_zero.core.site_capture_state import (
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_RUNNING,
    SiteCaptureProgress,
    SiteCaptureRequest,
    SiteCaptureResult,
    SiteCaptureState,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/site_capture_engine.py'

DATA_KEY_BY_MODE = {
    'cadastro': 'df_site_bruto_cadastro',
    'estoque': 'df_site_bruto_estoque',
    'atualizacao_preco': 'df_site_bruto_preco',
    'universal': 'df_site_bruto_universal',
}

ORIGIN_KEY_BY_MODE = {
    'cadastro': 'df_origem_site_como_planilha_cadastro',
    'estoque': 'df_origem_site_como_planilha_estoque',
    'atualizacao_preco': 'df_origem_site_como_planilha_preco',
    'universal': 'df_origem_site_como_planilha_universal',
}


@dataclass(frozen=True)
class SiteCaptureCommandResult:
    state: SiteCaptureState
    data_key: str = ''
    origin_key: str = ''
    needs_rerun: bool = False
    message: str = ''


def _shape(value: Any) -> tuple[int, int]:
    shape = getattr(value, 'shape', None)
    if isinstance(shape, tuple) and len(shape) >= 2:
        return int(shape[0] or 0), int(shape[1] or 0)
    columns = getattr(value, 'columns', None)
    if columns is not None:
        try:
            return len(value), len(columns)
        except Exception:
            return 0, 0
    if isinstance(value, list):
        if value and isinstance(value[0], Mapping):
            keys = set()
            for row in value:
                keys.update(dict(row).keys())
            return len(value), len(keys)
        return len(value), 0
    return 0, 0


def _columns(value: Any) -> tuple[str, ...]:
    columns = getattr(value, 'columns', None)
    if columns is not None:
        try:
            return tuple(str(col) for col in list(columns))
        except Exception:
            return tuple()
    if isinstance(value, list) and value and isinstance(value[0], Mapping):
        keys: list[str] = []
        for row in value:
            for key in dict(row).keys():
                text = str(key)
                if text not in keys:
                    keys.append(text)
        return tuple(keys)
    return tuple()


def data_key_for_mode(mode: str) -> str:
    return DATA_KEY_BY_MODE.get(str(mode or '').strip(), 'df_site_bruto')


def origin_key_for_mode(mode: str) -> str:
    return ORIGIN_KEY_BY_MODE.get(str(mode or '').strip(), 'df_origem_site_como_planilha')


def start_capture(request: SiteCaptureRequest) -> SiteCaptureCommandResult:
    progress = SiteCaptureProgress(status=STATUS_RUNNING, current_step='preparando', message='Preparando captura do site...', percent=1)
    state = SiteCaptureState(request=request, progress=progress)
    return SiteCaptureCommandResult(state, data_key_for_mode(request.mode), origin_key_for_mode(request.mode), True, progress.message)


def finish_capture(request: SiteCaptureRequest, data: Any, *, report_key: str = '', message: str = '') -> SiteCaptureCommandResult:
    rows, _cols = _shape(data)
    columns = _columns(data)
    data_key = data_key_for_mode(request.mode)
    origin_key = origin_key_for_mode(request.mode)
    progress = SiteCaptureProgress(status=STATUS_DONE, current_step='concluido', message=message or f'Captura concluída com {rows} produtos.', percent=100, rows=rows)
    result = SiteCaptureResult(status=STATUS_DONE, rows=rows, columns=columns, data_key=data_key, report_key=report_key, message=progress.message)
    state = SiteCaptureState(request=request, progress=progress, result=result)
    return SiteCaptureCommandResult(state, data_key, origin_key, True, progress.message)


def fail_capture(request: SiteCaptureRequest, error: object) -> SiteCaptureCommandResult:
    text = str(error or 'Erro desconhecido na captura.').strip()
    progress = SiteCaptureProgress(status=STATUS_ERROR, current_step='erro', message=text, percent=0, errors=(text,))
    result = SiteCaptureResult(status=STATUS_ERROR, error=text, message=text)
    state = SiteCaptureState(request=request, progress=progress, result=result)
    return SiteCaptureCommandResult(state, data_key_for_mode(request.mode), origin_key_for_mode(request.mode), True, text)


def build_capture_report(result: SiteCaptureCommandResult) -> dict[str, Any]:
    return {
        'status': result.state.result.status or result.state.progress.status,
        'message': result.message,
        'rows': result.state.result.rows,
        'columns': list(result.state.result.columns),
        'data_key': result.data_key,
        'origin_key': result.origin_key,
        'url': result.state.request.url,
        'mode': result.state.request.mode,
    }


__all__ = [
    'DATA_KEY_BY_MODE',
    'ORIGIN_KEY_BY_MODE',
    'SiteCaptureCommandResult',
    'build_capture_report',
    'data_key_for_mode',
    'fail_capture',
    'finish_capture',
    'origin_key_for_mode',
    'start_capture',
]
