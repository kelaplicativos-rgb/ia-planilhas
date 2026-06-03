from __future__ import annotations

from dataclasses import dataclass

from bling_app_zero.core.ai_runtime_context import get_secret_value, remaining_ai_session_calls

RESPONSIBLE_FILE = 'bling_app_zero/core/ai_mapping_availability.py'


@dataclass(frozen=True)
class AIMappingAvailability:
    enabled: bool
    remaining_calls: int
    reason: str = ''


def ai_mapping_enabled() -> bool:
    return bool(get_secret_value('OPENAI_API_KEY'))


def ai_mapping_remaining_session_calls() -> int:
    return remaining_ai_session_calls()


def ai_mapping_availability() -> AIMappingAvailability:
    enabled = ai_mapping_enabled()
    remaining = ai_mapping_remaining_session_calls()
    if not enabled:
        return AIMappingAvailability(False, remaining, 'OPENAI_API_KEY ausente')
    if remaining <= 0:
        return AIMappingAvailability(True, 0, 'limite de IA da sessão atingido')
    return AIMappingAvailability(True, remaining, 'ok')


__all__ = [
    'AIMappingAvailability',
    'RESPONSIBLE_FILE',
    'ai_mapping_availability',
    'ai_mapping_enabled',
    'ai_mapping_remaining_session_calls',
]
