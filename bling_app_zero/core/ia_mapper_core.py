# -*- coding: utf-8 -*-
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from .ia_mapper_config import (
    BLING_CADASTRO_FIELDS,
    BLING_ESTOQUE_FIELDS,
    FIELD_SYNONYMS,
    MULTI_SOURCE_ALLOWED_FIELDS,
    REQUIRED_FIELDS_CADASTRO,
    REQUIRED_FIELDS_ESTOQUE,
)
from .ia_mapper_models import MappingCandidate, MappingValidation
from .ia_mapper_text import is_image_like, normalize_text, simplify_token_set


def sequence_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def get_target_fields(mode: str) -> List[str]:
    mode = normalize_text(mode)
    if mode == "cadastro":
        return BLING_CADASTRO_FIELDS.copy()
    if mode == "estoque":
        return BLING_ESTOQUE_FIELDS.copy()
    raise ValueError(f"Modo inválido: {mode}. Use 'cadastro' ou 'estoque'.")


def get_required_fields(mode: str) -> List[str]:
    mode = normalize_text(mode)
    if mode == "cadastro":
        return REQUIRED_FIELDS_CADASTRO.copy()
    if mode == "estoque":
        return REQUIRED_FIELDS_ESTOQUE.copy()
    raise ValueError(f"Modo inválido: {mode}. Use 'cadastro' ou 'estoque'.")


def score_column_to_field(
    supplier_column: str,
    target_field: str,
) -> Tuple[float, str]:
    source_norm = normalize_text(supplier_column)
    field_norm = normalize_text(target_field)

    if not source_norm or not field_norm:
        return 0.0, "vazio"

    if source_norm == field_norm:
        return 1.0, "match exato"

    best_score = 0.0
    best_reason = "sem correspondencia"

    ratio_field = sequence_ratio(source_norm, field_norm)
    if ratio_field > best_score:
        best_score = ratio_field * 0.82
        best_reason = "similaridade nome campo"

    source_tokens = simplify_token_set(source_norm)
    field_tokens = simplify_token_set(field_norm)

    if source_tokens and field_tokens:
        inter = source_tokens.intersection(field_tokens)
        union = source_tokens.union(field_tokens)
        jacc = len(inter) / max(len(union), 1)
        token_score = jacc * 0.88
        if token_score > best_score:
            best_score = token_score
            best_reason = "tokens em comum"

    synonyms = FIELD_SYNONYMS.get(target_field, [])
    for synonym in synonyms:
        syn_norm = normalize_text(synonym)

        if source_norm == syn_norm:
            return 0.99, f"sinonimo exato: {synonym}"

        ratio_syn = sequence_ratio(source_norm, syn_norm)
        if ratio_syn * 0.95 > best_score:
            best_score = ratio_syn * 0.95
            best_reason = f"similaridade sinonimo: {synonym}"

        syn_tokens = simplify_token_set(syn_norm)
        if source_tokens and syn_tokens:
            inter = source_tokens.intersection(syn_tokens)
            union = source_tokens.union(syn_tokens)
            jacc = len(inter) / max(len(union), 1)
            token_score = jacc * 0.96
            if token_score > best_score:
                best_score = token_score
                best_reason = f"tokens sinonimo: {synonym}"

    if target_field.startswith("imagem") and is_image_like(source_norm):
        best_score = max(best_score, 0.93)
        best_reason = "coluna de imagem detectada"

    if target_field == "descricao curta":
        if any(k in source_norm for k in ["nome", "titulo", "title", "produto", "descricao"]):
            best_score = min(0.98, best_score + 0.08)
            best_reason = "ajuste descricao curta"

    if target_field == "descricao":
        if any(k in source_norm for k in ["nome", "titulo", "title", "produto"]):
            best_score = max(0.0, best_score - 0.06)

    if target_field in {"saldo", "estoque atual"}:
        if any(k in source_norm for k in ["estoque", "saldo", "qtd", "qtde", "quantidade"]):
            best_score = min(0.98, best_score + 0.05)
            best_reason = "ajuste estoque"

    return round(min(best_score, 1.0), 4), best_reason


def build_candidates(
    supplier_columns: List[str],
    mode: str,
    min_score: float = 0.45,
) -> List[MappingCandidate]:
    target_fields = get_target_fields(mode)
    candidates: List[MappingCandidate] = []

    for source_col in supplier_columns:
        for target_field in target_fields:
            score, reason = score_column_to_field(source_col, target_field)
            if score >= min_score:
                candidates.append(
                    MappingCandidate(
                        supplier_column=source_col,
                        target_field=target_field,
                        score=score,
                        reason=reason,
                    )
                )

    candidates.sort(
        key=lambda x: (x.score, len(normalize_text(x.supplier_column))),
        reverse=True,
    )
    return candidates


def post_adjust_mapping(
    mapping: Dict[str, Any],
    supplier_columns: List[str],
    mode: str,
) -> Dict[str, Any]:
    if normalize_text(mode) == "cadastro":
        for col in supplier_columns:
            n = normalize_text(col)
            if n in {
                "descricao do produto",
                "descrição do produto",
                "descricao curta",
                "nome produto",
                "titulo",
                "title",
                "nome",
                "produto",
            }:
                if not mapping.get("descricao curta"):
                    mapping["descricao curta"] = col
                break

    if mapping.get("url video"):
        source_video = mapping["url video"]
        if isinstance(source_video, str) and is_image_like(source_video):
            mapping["url video"] = ""

    image_sources: List[str] = []
    for field in ["imagem 1", "imagem 2", "imagem 3", "imagem 4", "imagem 5"]:
        value = mapping.get(field, [])
        if isinstance(value, str) and value:
            image_sources.append(value)
        elif isinstance(value, list):
            image_sources.extend([v for v in value if v])

    dedup_image_sources: List[str] = []
    seen = set()
    for col in image_sources:
        if col not in seen and col in supplier_columns:
            dedup_image_sources.append(col)
            seen.add(col)

    for idx, field in enumerate(["imagem 1", "imagem 2", "imagem 3", "imagem 4", "imagem 5"]):
        if idx < len(dedup_image_sources):
            mapping[field] = [dedup_image_sources[idx]]
        else:
            mapping[field] = []

    return mapping


def suggest_mapping(
    supplier_columns: List[str],
    mode: str,
    min_score: float = 0.45,
    existing_profile_mapping: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    target_fields = get_target_fields(mode)
    candidates = build_candidates(supplier_columns, mode, min_score=min_score)

    mapping: Dict[str, Any] = {field: "" for field in target_fields}
    used_source_columns = set()

    if existing_profile_mapping:
        for field in target_fields:
            if field not in existing_profile_mapping:
                continue

            saved = existing_profile_mapping[field]

            if field in MULTI_SOURCE_ALLOWED_FIELDS:
                if isinstance(saved, list):
                    valid_multi = [col for col in saved if col in supplier_columns]
                    if valid_multi:
                        mapping[field] = valid_multi
                        used_source_columns.update(valid_multi)
                elif isinstance(saved, str) and saved in supplier_columns:
                    mapping[field] = [saved]
                    used_source_columns.add(saved)
            else:
                if isinstance(saved, str) and saved in supplier_columns:
                    mapping[field] = saved
                    used_source_columns.add(saved)

    for cand in candidates:
        field = cand.target_field
        source = cand.supplier_column

        if field in MULTI_SOURCE_ALLOWED_FIELDS:
            current = mapping.get(field, "")
            if not current:
                mapping[field] = []

            current = mapping[field]
            if not isinstance(current, list):
                current = [current] if current else []
                mapping[field] = current

            if source not in current:
                current.append(source)
            continue

        if mapping.get(field):
            continue

        if source in used_source_columns:
            continue

        mapping[field] = source
        used_source_columns.add(source)

    mapping = post_adjust_mapping(mapping, supplier_columns, mode)
    return mapping


def get_field_candidates(
    supplier_columns: List[str],
    mode: str,
    target_field: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for source_col in supplier_columns:
        score, reason = score_column_to_field(source_col, target_field)
        candidates.append(
            {
                "supplier_column": source_col,
                "target_field": target_field,
                "score": score,
                "reason": reason,
            }
        )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_k]


def clean
