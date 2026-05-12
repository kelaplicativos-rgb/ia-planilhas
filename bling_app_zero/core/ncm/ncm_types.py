from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NcmSuggestion:
    ncm: str
    confidence: str
    score: int
    source: str
    reason: str

    @property
    def should_apply(self) -> bool:
        return bool(self.ncm) and self.confidence == 'alta' and self.score >= 82


EMPTY_NCM_SUGGESTION = NcmSuggestion(
    ncm='',
    confidence='baixa',
    score=0,
    source='none',
    reason='Sem sugestão segura.',
)


__all__ = ['EMPTY_NCM_SUGGESTION', 'NcmSuggestion']
