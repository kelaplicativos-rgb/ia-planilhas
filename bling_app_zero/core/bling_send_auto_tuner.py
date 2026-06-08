from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_send_auto_tuner.py'

MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 5
TARGET_BATCH_SECONDS = 12.0
SLOW_BATCH_SECONDS = 20.0
VERY_FAST_BATCH_SECONDS = 4.0


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


def _clamp_batch_size(value: int) -> int:
    return max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, int(value or MIN_BATCH_SIZE)))


def initial_batch_size(operation: object) -> int:
    op = normalize_operation(operation)
    if op == OP_CADASTRO:
        return 2
    if op == OP_ESTOQUE:
        return 3
    if op == OP_ATUALIZACAO_PRECO:
        return 3
    return 2


def intelligent_batch_size(
    operation: object,
    *,
    current_batch_size: int | None = None,
    last_batch_seconds: float | None = None,
    last_failed: int = 0,
    last_skipped: int = 0,
) -> IntelligentSendPlan:
    op = normalize_operation(operation)
    current = _clamp_batch_size(current_batch_size or initial_batch_size(op))
    failed = max(0, int(last_failed or 0))
    skipped = max(0, int(last_skipped or 0))

    if failed > 0:
        return IntelligentSendPlan(op, max(MIN_BATCH_SIZE, current - 1), 'falha detectada no lote anterior; reduzindo automaticamente para proteger a API')

    seconds = float(last_batch_seconds or 0.0)
    if seconds <= 0:
        return IntelligentSendPlan(op, current, 'início automático com velocidade moderada')
    if seconds >= SLOW_BATCH_SECONDS:
        return IntelligentSendPlan(op, max(MIN_BATCH_SIZE, current - 1), 'Bling respondeu devagar; reduzindo velocidade automaticamente')
    if seconds <= VERY_FAST_BATCH_SECONDS and skipped == 0:
        return IntelligentSendPlan(op, min(MAX_BATCH_SIZE, current + 1), 'Bling respondeu rápido; acelerando com segurança')
    return IntelligentSendPlan(op, current, 'velocidade mantida automaticamente pelo desempenho do último lote')


def progress_caption(plan: IntelligentSendPlan) -> str:
    return f'{plan.label}: sistema ajustando velocidade sozinho · lote {plan.batch_size} · {plan.reason}.'


__all__ = [
    'IntelligentSendPlan',
    'initial_batch_size',
    'intelligent_batch_size',
    'progress_caption',
]
