from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bling_app_zero.core.bling_send_state import (
    STATUS_DONE,
    STATUS_IDLE,
    STATUS_PAUSED,
    STATUS_RUNNING,
    BlingSendRequest,
    BlingSendState,
    batch_size_for_operation,
    normalize_operation,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_send_engine.py'
NO_PROGRESS_GUARD_MESSAGE = (
    'Envio pausado por segurança: o último lote não teve avanço '
    '(0 enviados, 0 falhas e todas as linhas ignoradas). '
    'Revise mapeamento/identificador/quantidade ou clique em Reiniciar envio.'
)


@dataclass(frozen=True)
class BlingSendCommandResult:
    state: BlingSendState
    message: str = ''
    needs_rerun: bool = False


def create_send_state(*, identity: str, total: int, operation: str) -> BlingSendState:
    normalized = normalize_operation(operation)
    request = BlingSendRequest(identity=identity, operation=normalized, total=int(total or 0), batch_size=batch_size_for_operation(normalized))
    return BlingSendState(request=request, status=STATUS_IDLE)


def ensure_send_state(current: dict[str, Any] | BlingSendState | None, *, identity: str, total: int, operation: str) -> BlingSendState:
    if isinstance(current, BlingSendState):
        state = current
    elif isinstance(current, dict):
        state = BlingSendState.from_mapping(current)
    else:
        state = create_send_state(identity=identity, total=total, operation=operation)
    if state.request.identity != identity:
        return create_send_state(identity=identity, total=total, operation=operation)
    return state


def start_auto_send(state: BlingSendState) -> BlingSendCommandResult:
    if state.done:
        return BlingSendCommandResult(state, 'Envio já concluído.', False)
    next_state = BlingSendState.from_mapping({**state.to_dict(), 'started': True, 'auto_running': True, 'paused': False, 'status': STATUS_RUNNING})
    return BlingSendCommandResult(next_state, 'Envio automático iniciado.', True)


def pause_send(state: BlingSendState) -> BlingSendCommandResult:
    next_state = BlingSendState.from_mapping({**state.to_dict(), 'auto_running': False, 'paused': True, 'status': STATUS_PAUSED})
    return BlingSendCommandResult(next_state, 'Envio pausado.', True)


def reset_send(*, identity: str, total: int, operation: str) -> BlingSendCommandResult:
    return BlingSendCommandResult(create_send_state(identity=identity, total=total, operation=operation), 'Envio reiniciado.', True)


def mark_manual_batch_mode(state: BlingSendState) -> BlingSendCommandResult:
    next_state = BlingSendState.from_mapping({**state.to_dict(), 'started': True, 'auto_running': False, 'paused': True, 'status': STATUS_PAUSED})
    return BlingSendCommandResult(next_state, 'Envio de um lote preparado.', True)


def _batch_has_no_progress(result: Any) -> bool:
    attempted = int(getattr(result, 'attempted', 0) or 0)
    sent = int(getattr(result, 'sent', 0) or 0)
    failed = int(getattr(result, 'failed', 0) or 0)
    skipped = int(getattr(result, 'skipped', 0) or 0)
    return attempted > 0 and sent == 0 and failed == 0 and skipped >= attempted


def append_batch_result(state: BlingSendState, result: Any, *, batch_start: int, batch_end: int) -> BlingSendCommandResult:
    result_attempted = int(getattr(result, 'attempted', 0) or 0)
    result_sent = int(getattr(result, 'sent', 0) or 0)
    result_failed = int(getattr(result, 'failed', 0) or 0)
    result_skipped = int(getattr(result, 'skipped', 0) or 0)

    attempted = state.attempted + result_attempted
    sent = state.sent + result_sent
    failed = state.failed + result_failed
    skipped = state.skipped + result_skipped
    errors = list(state.errors) + [str(item) for item in list(getattr(result, 'errors', ()) or ())]
    not_found = list(state.not_found_indices)
    for item in list(getattr(result, 'not_found_indices', ()) or ()):
        try:
            not_found.append(int(batch_start) + int(item))
        except Exception:
            pass

    if _batch_has_no_progress(result):
        guard_message = (
            f'{NO_PROGRESS_GUARD_MESSAGE} '
            f'Lote bloqueado: linhas {int(batch_start) + 1}-{int(batch_end)}.'
        )
        next_state = BlingSendState.from_mapping(
            {
                **state.to_dict(),
                # Não avança offset: mantém o lote problemático visível para correção/reenvio.
                'offset': int(batch_start),
                'attempted': attempted,
                'sent': sent,
                'failed': failed,
                'skipped': skipped,
                'errors': (errors + [guard_message])[:80],
                'not_found_indices': sorted(set(not_found)),
                'done': False,
                'auto_running': False,
                'paused': True,
                'status': STATUS_PAUSED,
            }
        )
        return BlingSendCommandResult(next_state, guard_message, True)

    done = int(batch_end) >= int(state.request.total)
    status = STATUS_DONE if done else (STATUS_RUNNING if state.auto_running else STATUS_PAUSED)
    next_state = BlingSendState.from_mapping(
        {
            **state.to_dict(),
            'offset': int(batch_end),
            'attempted': attempted,
            'sent': sent,
            'failed': failed,
            'skipped': skipped,
            'errors': errors[:80],
            'not_found_indices': sorted(set(not_found)),
            'done': done,
            'auto_running': False if done else state.auto_running,
            'paused': False if done else state.paused,
            'status': status,
        }
    )
    return BlingSendCommandResult(next_state, 'Resultado do lote acumulado.', done)


def result_payload(state: BlingSendState) -> dict[str, Any]:
    return {
        'attempted': int(state.attempted),
        'sent': int(state.sent),
        'failed': int(state.failed),
        'skipped': int(state.skipped),
        'errors': list(state.errors),
        'not_found_indices': list(state.not_found_indices),
    }


__all__ = [
    'BlingSendCommandResult',
    'append_batch_result',
    'create_send_state',
    'ensure_send_state',
    'mark_manual_batch_mode',
    'pause_send',
    'reset_send',
    'result_payload',
    'start_auto_send',
]
