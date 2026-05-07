from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .smart_fields import FieldRequest, normalize_column_name


@dataclass(frozen=True)
class MappingSuggestion:
    target_column: str
    source_kind: str
    confidence: float
    reason: str


def suggest_mapping(field_requests: list[FieldRequest], extracted_keys: list[str] | None = None) -> list[MappingSuggestion]:
    """Sugere como os dados extraídos devem preencher o modelo.

    É uma IA heurística local e segura: não chama API externa e não altera o
    fluxo antigo. Ela serve para o motor FLASH entender a intenção das colunas.
    """

    available = {normalize_column_name(key) for key in (extracted_keys or [])}
    suggestions: list[MappingSuggestion] = []

    for field in field_requests:
        confidence = 0.88 if field.kind != "custom" else 0.35
        reason = "campo reconhecido por alias do modelo Bling"

        if field.kind == "custom":
            reason = "campo personalizado sem alias conhecido; manter vazio se não encontrado"
        elif available and normalize_column_name(field.kind) not in available:
            confidence = min(confidence, 0.72)
            reason = "campo solicitado pela planilha; extração depende do conteúdo encontrado no site"

        suggestions.append(
            MappingSuggestion(
                target_column=field.original_name,
                source_kind=field.kind,
                confidence=confidence,
                reason=reason,
            )
        )

    return suggestions


def suggestions_as_dict(field_requests: list[FieldRequest], extracted: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    keys = list((extracted or {}).keys())
    return [suggestion.__dict__ for suggestion in suggest_mapping(field_requests, keys)]
