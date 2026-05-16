from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AIMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AIResult:
    ok: bool
    task: str
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ''
    error: str = ''


@dataclass(frozen=True)
class AIJob:
    job_id: str
    task: str
    payload: dict[str, Any]
    status: str = 'pendente'
    result: AIResult | None = None


@dataclass(frozen=True)
class ColumnProfile:
    column: str
    detected_kind: str
    confidence: float
    sample_values: list[str] = field(default_factory=list)
    reason: str = ''


@dataclass(frozen=True)
class MappingSuggestion:
    target_column: str
    source_column: str
    confidence: float
    reason: str = ''


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    column: str
    row_index: int | None
    message: str


__all__ = [
    'AIJob',
    'AIMessage',
    'AIResult',
    'ColumnProfile',
    'MappingSuggestion',
    'QualityIssue',
]
