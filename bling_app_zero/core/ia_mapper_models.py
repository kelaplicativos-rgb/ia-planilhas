# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MappingCandidate:
    supplier_column: str
    target_field: str
    score: float
    reason: str


@dataclass
class MappingValidation:
    missing_required: List[str] = field(default_factory=list)
    duplicate_source_columns: List[str] = field(default_factory=list)
    duplicate_target_fields: List[str] = field(default_factory=list)
    invalid_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_valid: bool = True


@dataclass
class MappingProfile:
    supplier_name: str
    mode: str
    mapping: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
