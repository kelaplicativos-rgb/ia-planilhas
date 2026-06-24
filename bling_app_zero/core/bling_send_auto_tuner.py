from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bling_app_zero.core.operation_contract import (
    OP_ATUALIZACAO_PRECO,
    OP_CADASTRO,
    OP_ESTOQUE,
    OP_UNIVERSAL,
    normalize_operation,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_send_auto_tuner.py'

MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 12
TARGET_BATCH_SECONDS = 18.0
SLOW_BATCH_SECONDS = 36.0
VERY_FAST_BATCH_SECONDS = 8.0
FAST_BATCH_SECONDS = 16.0

# BLINGPERF: perfil único inteligente por operação.
# O usuário não escolhe modo seguro/rápido/turbo. O sistema mede o retorno da API
# e ajusta sozinho. Cadastro, preços/multiloja e estoque usam o mesmo perfil rápido
# controlado; se o Bling responder mal ou houver falha, reduz sozinho.
OPERATION_BATCH_PROFILE: dict[str, dict[str, int]] = {
    OP_CADASTRO: {'initial': 6, 'max': 10},
    OP_ESTOQUE: {'initial': 6, 'max': 10},
    OP_ATUALIZACAO_PRECO: {'initial': 6, 'max': 10},
    OP_UNIVERSAL: {'initial': 6, 'max': 10},
}


@dataclass(frozen=True)
class IntelligentSendPlan:
    operation: str
    batch_size: int
    reason: str
    label: str = 'Modo inteligente automático'

    def to_dict(self) -> dict[str, Any]:
        return {
            'operation': self.operation,
            'batch_size': int(self.batch_size),
            'reason': self.reason,
            'label': self.label,
            'responsible_file': RESPONSIBLE_FILE,
        }


def _profile(operation: object) -> dict[str, int]:
    op = normalize_operation(operation)
    return OPERATION_BATCH_PROFILE.get(op, OPERATION_BATCH_PROFILE[OP_UNIVERSAL])


def _operation_max_batch_size(operation: object) -> int:
    profile = _profile(operation)
    value = int(profile.get('max') or MAX_BATCH_SIZE)
    return max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, value))


def _clamp_batch_size(value: int, *, operation: object) -> int:
    return max(MIN_BATCH_SIZE, min(_operation_max_batch_size(operation), int(value or MIN_BATCH_SIZE)))


def initial_batch_size(operation: object) -> int:
    profile = _profile(operation)
    return _clamp_batch_size(int(profile.get('initial') or 6), operation=operation)


def intelligent_batch_size(
    operation: object,
    *,
    current_batch_size: int | None = None,
    last_batch_seconds: float | None = None,
    last_failed: int = 0,
    last_skipped: int = 0,
) -> IntelligentSendPlan:
    op = normalize_operation(operation)
    current = _clamp_batch_size(current_batch_size or initial_batch_size(op), operation=op)
    failed = max(0, int(last_failed or 0))
    skipped = max(0, int(last_skipped or 0))

    if failed > 0:
        return IntelligentSendPlan(
            op,
            max(MIN_BATCH_SIZE, current - max(1, min(3, failed))),
            'falha detectada no lote anterior; reduzindo automaticamente para proteger a API',
        )

    seconds = float(last_batch_seconds or 0.0)
    if seconds <= 0:
        return IntelligentSendPlan(op, current, 'início automático em lote rápido controlado')
    if seconds >= SLOW_BATCH_SECONDS:
        return IntelligentSendPlan(
            op,
            max(MIN_BATCH_SIZE, current - 2),
            'Bling respondeu devagar; reduzindo velocidade automaticamente',
        )
    if seconds <= VERY_FAST_BATCH_SECONDS and skipped == 0:
        return IntelligentSendPlan(
            op,
            _clamp_batch_size(current + 2, operation=op),
            'Bling respondeu muito rápido; acelerando com segurança',
        )
    if seconds <= FAST_BATCH_SECONDS and skipped == 0:
        return IntelligentSendPlan(
            op,
            _clamp_batch_size(current + 1, operation=op),
            'Bling respondeu bem; aumentando levemente o lote',
        )
    return IntelligentSendPlan(op, current, 'velocidade mantida automaticamente pelo desempenho do último lote')


def progress_caption(plan: IntelligentSendPlan) -> str:
    return f'{plan.label}: sistema ajustando velocidade sozinho · lote {plan.batch_size} · {plan.reason}.'


__all__ = [
    'IntelligentSendPlan',
    'OPERATION_BATCH_PROFILE',
    'initial_batch_size',
    'intelligent_batch_size',
    'progress_caption',
]
