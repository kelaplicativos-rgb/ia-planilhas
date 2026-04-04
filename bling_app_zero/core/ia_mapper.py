# -*- coding: utf-8 -*-
"""
core/mapper.py

Motor de mapeamento inteligente entre:
- colunas da planilha do fornecedor
- colunas do modelo Bling (cadastro ou estoque)

Recursos:
- sugestão automática por heurística
- bloqueio de duplicidade
- validação de obrigatórios
- perfil salvo por fornecedor
- reaproveitamento automático de mapeamento salvo
- suporte a múltiplas colunas para imagens
- utilitários para integração com app.py
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple, Any


# =========================================================
# CONFIG
# =========================================================

DEFAULT_PROFILE_DIR = os.path.join("data", "mapeamentos")


# =========================================================
# MODELOS E CAMPOS
# =========================================================

# Ajuste livre: mantenha aqui apenas os campos que realmente quer usar
# no seu fluxo. Você pode aumentar depois sem quebrar o módulo.

BLING_CADASTRO_FIELDS: List[str] = [
    "codigo",
    "descricao",
    "descricao curta",
    "descricao complementar",
    "marca",
    "categoria",
    "unidade",
    "preco",
    "preco promocional",
    "custo",
    "ncm",
    "origem",
    "gtin",
    "gtin embalagem",
    "peso liquido (kg)",
    "peso bruto (kg)",
    "largura (cm)",
    "altura (cm)",
    "profundidade (cm)",
    "estoque minimo",
    "estoque maximo",
    "estoque atual",
    "localizacao",
    "fornecedor",
    "codigo fornecedor",
    "slug",
    "url video",
    "imagem 1",
    "imagem 2",
    "imagem 3",
    "imagem 4",
    "imagem 5",
    "observacoes",
]

BLING_ESTOQUE_FIELDS: List[str] = [
    "codigo",
    "descricao",
    "deposito",
    "saldo",
    "saldo virtual",
    "estoque minimo",
    "estoque maximo",
    "localizacao",
]

REQUIRED_FIELDS_CADASTRO: List[str] = [
    "codigo",
    "descricao curta",
]

REQUIRED_FIELDS_ESTOQUE: List[str] = [
    "codigo",
    "deposito",
    "saldo",
]


# =========================================================
# SINÔNIMOS / HEURÍSTICAS
# =========================================================

# Quanto mais rico aqui, melhor fica o auto-mapeamento.
FIELD_SYNONYMS: Dict[str, List[str]] = {
    "codigo": [
        "codigo",
        "cod",
        "sku",
        "referencia",
        "ref",
        "cod produto",
        "codigo produto",
        "id produto",
        "part number",
        "pn",
        "codigo interno",
        "codigo pai",
    ],
    "descricao": [
        "descricao",
        "descrição",
        "nome",
        "produto",
        "nome produto",
        "titulo",
        "title",
    ],
    "descricao curta": [
        "descricao curta",
        "descrição curta",
        "descricao do produto",
        "descrição do produto",
        "nome",
        "titulo",
        "title",
        "produto",
        "nome produto",
    ],
    "descricao complementar": [
        "descricao complementar",
        "descrição complementar",
        "descricao longa",
        "descrição longa",
        "texto longo",
        "detalhes",
        "informacoes",
        "informações",
    ],
    "marca": [
        "marca",
        "brand",
        "fabricante",
    ],
    "categoria": [
        "categoria",
        "departamento",
        "grupo",
        "tipo",
        "segmento",
        "colecao",
        "coleção",
    ],
    "unidade": [
        "unidade",
        "und",
        "un",
        "unit",
    ],
    "preco": [
        "preco",
        "preço",
        "valor",
        "valor venda",
        "preco venda",
        "preço venda",
        "venda",
        "price",
    ],
    "preco promocional": [
        "preco promocional",
        "preço promocional",
        "preco promo",
        "preço promo",
        "promocional",
        "promo",
        "sale price",
    ],
    "custo": [
        "custo",
        "valor custo",
        "preco custo",
        "preço custo",
        "cost",
    ],
    "ncm": [
        "ncm",
        "classificacao fiscal",
        "classificação fiscal",
    ],
    "origem": [
        "origem",
        "origem mercadoria",
    ],
    "gtin": [
        "gtin",
        "ean",
        "ean13",
        "codigo de barras",
        "código de barras",
        "barcode",
        "gtin/ean",
    ],
    "gtin embalagem": [
        "gtin embalagem",
        "ean embalagem",
        "codigo barras embalagem",
        "código barras embalagem",
        "barcode embalagem",
    ],
    "peso liquido (kg)": [
        "peso liquido",
        "peso líquido",
        "peso",
        "peso liq",
        "peso liquido kg",
        "peso líquido kg",
    ],
    "peso bruto (kg)": [
        "peso bruto",
        "peso bruto kg",
    ],
    "largura (cm)": [
        "largura",
        "width",
        "largura cm",
    ],
    "altura (cm)": [
        "altura",
        "height",
        "altura cm",
    ],
    "profundidade (cm)": [
        "profundidade",
        "comprimento",
        "length",
        "depth",
        "profundidade cm",
        "comprimento cm",
    ],
    "estoque minimo": [
        "estoque minimo",
        "estoque mínimo",
        "minimo",
        "mínimo",
        "estoque min",
        "estoque mínimo ideal",
    ],
    "estoque maximo": [
        "estoque maximo",
        "estoque máximo",
        "maximo",
        "máximo",
        "estoque max",
    ],
    "estoque atual": [
        "estoque",
        "quantidade",
        "qtd",
        "saldo",
        "estoque atual",
        "qtde",
        "quant",
        "disponivel",
        "disponível",
    ],
    "saldo": [
        "saldo",
        "estoque",
        "quantidade",
        "qtd",
        "qtde",
        "saldo atual",
        "estoque atual",
    ],
    "saldo virtual": [
        "saldo virtual",
        "estoque virtual",
        "virtual",
    ],
    "deposito": [
        "deposito",
        "depósito",
        "deposito id",
        "depósito id",
        "id deposito",
        "id depósito",
        "warehouse",
    ],
    "localizacao": [
        "localizacao",
        "localização",
        "rua",
        "prateleira",
        "endereco estoque",
        "posição",
        "posicao",
    ],
    "fornecedor": [
        "fornecedor",
        "supplier",
        "fabricante",
        "distribuidor",
    ],
    "codigo fornecedor": [
        "codigo fornecedor",
        "código fornecedor",
        "ref fornecedor",
        "referencia fornecedor",
        "sku fornecedor",
        "codigo do fornecedor",
    ],
    "slug": [
        "slug",
        "url amigavel",
        "url amigável",
        "handle",
    ],
    "url video": [
        "video",
        "vídeo",
        "url video",
        "url vídeo",
        "youtube",
        "link video",
        "link vídeo",
    ],
    "imagem 1": [
        "imagem",
        "img",
        "foto",
        "image",
        "imagem 1",
        "foto 1",
        "link imagem",
        "url imagem",
        "imagem principal",
    ],
    "imagem 2": [
        "imagem 2",
        "foto 2",
        "img 2",
        "image 2",
    ],
    "imagem 3": [
        "imagem 3",
        "foto 3",
        "img 3",
        "image 3",
    ],
    "imagem 4": [
        "imagem 4",
        "foto 4",
        "img 4",
        "image 4",
    ],
    "imagem 5": [
        "imagem 5",
        "foto 5",
        "img 5",
        "image 5",
    ],
    "observacoes": [
        "observacoes",
        "observações",
        "obs",
        "comentario",
        "comentário",
        "notas",
    ],
}


# Campos que podem aceitar múltiplas colunas do fornecedor
# Ex.: várias colunas de imagem mapeadas para uma única saída.
MULTI_SOURCE_ALLOWED_FIELDS = {
    "imagem 1",
    "imagem 2",
    "imagem 3",
    "imagem 4",
    "imagem 5",
}

IMAGE_KEYWORDS = {
    "imagem", "img", "foto", "image", "images", "fotos", "url imagem", "link imagem"
}


# =========================================================
# DATA CLASSES
# =========================================================

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
    mode: str  # cadastro | estoque
    mapping: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# =========================================================
# NORMALIZAÇÃO
# =========================================================

def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = re.sub(r"[_/\\\-]+", " ", text)
    text = re.sub(r"[^a-z0-9\s\(\)]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def simplify_token_set(text: str) -> set:
    return set(normalize_text(text).split())


def is_image_like(text: str) -> bool:
    tokens = simplify_token_set(text)
    return bool(tokens.intersection(IMAGE_KEYWORDS))


def sequence_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


# =========================================================
# CAMPOS POR MODO
# =========================================================

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


# =========================================================
# SCORE DE SIMILARIDADE
# =========================================================

def score_column_to_field(
    supplier_column: str,
    target_field: str,
) -> Tuple[float, str]:
    source_norm = normalize_text(supplier_column)
    field_norm = normalize_text(target_field)

    if not source_norm or not field_norm:
        return 0.0, "vazio"

    # match exato
    if source_norm == field_norm:
        return 1.0, "match exato"

    best_score = 0.0
    best_reason = "sem correspondencia"

    # similaridade direta com nome do campo
    ratio_field = sequence_ratio(source_norm, field_norm)
    if ratio_field > best_score:
        best_score = ratio_field * 0.82
        best_reason = "similaridade nome campo"

    # tokens em comum
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

    # sinônimos
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

    # reforço para imagens
    if target_field.startswith("imagem") and is_image_like(source_norm):
        best_score = max(best_score, 0.93)
        best_reason = "coluna de imagem detectada"

    # penalização para ambiguidades comuns
    if target_field == "descricao curta":
        # Queremos favorecer nome/título/produto
        if any(k in source_norm for k in ["nome", "titulo", "title", "produto", "descricao"]):
            best_score = min(0.98, best_score + 0.08)
            best_reason = "ajuste descricao curta"

    if target_field == "descricao":
        # reduz chance de competir com descricao curta
        if any(k in source_norm for k in ["nome", "titulo", "title", "produto"]):
            best_score = max(0.0, best_score - 0.06)

    if target_field in {"saldo", "estoque atual"}:
        if any(k in source_norm for k in ["estoque", "saldo", "qtd", "qtde", "quantidade"]):
            best_score = min(0.98, best_score + 0.05)
            best_reason = "ajuste estoque"

    return round(min(best_score, 1.0), 4), best_reason


# =========================================================
# CANDIDATOS E SUGESTÕES
# =========================================================

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

    candidates.sort(key=lambda x: (x.score, len(normalize_text(x.supplier_column))), reverse=True)
    return candidates


def suggest_mapping(
    supplier_columns: List[str],
    mode: str,
    min_score: float = 0.45,
    existing_profile_mapping: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retorna dict no formato:
    {
        "codigo": "SKU",
        "descricao curta": "Nome Produto",
        "imagem 1": ["Imagem 1", "Imagem Principal"],
        ...
    }
    """
    target_fields = get_target_fields(mode)
    candidates = build_candidates(supplier_columns, mode, min_score=min_score)

    mapping: Dict[str, Any] = {field: "" for field in target_fields}
    used_source_columns = set()

    # 1) reaproveita perfil salvo, se existir
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

    # 2) auto sugestão por score
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

            # imagens aceitam múltiplas origens
            if source not in current:
                current.append(source)
            continue

        # demais campos não podem duplicar origem
        if mapping.get(field):
            continue
        if source in used_source_columns:
            continue

        mapping[field] = source
        used_source_columns.add(source)

    # 3) pós-ajustes
    mapping = post_adjust_mapping(mapping, supplier_columns, mode)

    return mapping


def post_adjust_mapping(
    mapping: Dict[str, Any],
    supplier_columns: List[str],
    mode: str,
) -> Dict[str, Any]:
    """
    Regras finas para melhorar o mapeamento.
    """
    supplier_norm_map = {normalize_text(col): col for col in supplier_columns}

    # regra importante do projeto:
    # "descrição do produto" vai para "descricao curta"
    if mode == "cadastro":
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

        # Evita jogar vídeo em url de imagem ou vice-versa
        if mapping.get("url video"):
            source_video = mapping["url video"]
            if isinstance(source_video, str) and is_image_like(source_video):
                mapping["url video"] = ""

        # Reorganiza imagens em ordem
        image_sources = []
        for field in ["imagem 1", "imagem 2", "imagem 3", "imagem 4", "imagem 5"]:
            value = mapping.get(field, [])
            if isinstance(value, str) and value:
                image_sources.append(value)
            elif isinstance(value, list):
                image_sources.extend([v for v in value if v])

        # dedup preservando ordem
        dedup_image_sources = []
        seen = set()
        for col in image_sources:
            if col not in seen and col in supplier_columns:
                dedup_image_sources.append(col)
                seen.add(col)

        # redistribui
        for idx, field in enumerate(["imagem 1", "imagem 2", "imagem 3", "imagem 4", "imagem 5"]):
            if idx < len(dedup_image_sources):
                mapping[field] = [dedup_image_sources[idx]]
            else:
                mapping[field] = []

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


# =========================================================
# DUPLICIDADE / LIMPEZA DE MAPEAMENTO
# =========================================================

def clean_mapping(mapping: Dict[str, Any], mode: str) -> Dict[str, Any]:
    target_fields = get_target_fields(mode)
    cleaned: Dict[str, Any] = {}

    for field in target_fields:
        value = mapping.get(field, "")

        if field in MULTI_SOURCE_ALLOWED_FIELDS:
            if isinstance(value, list):
                unique_list = []
                seen = set()
                for item in value:
                    if item and item not in seen:
                        unique_list.append(item)
                        seen.add(item)
                cleaned[field] = unique_list
            elif isinstance(value, str) and value.strip():
                cleaned[field] = [value.strip()]
            else:
                cleaned[field] = []
        else:
            cleaned[field] = value.strip() if isinstance(value, str) else ""

    return cleaned


def remove_duplicate_assignments(mapping: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """
    Garante que a mesma coluna do fornecedor não seja usada em dois campos normais.
    Imagens podem repetir internamente apenas se vierem em lista, mas vamos deduplicar.
    """
    mapping = clean_mapping(mapping, mode)
    used_sources = {}
    resolved: Dict[str, Any] = {}

    for field in get_target_fields(mode):
        value = mapping.get(field, [] if field in MULTI_SOURCE_ALLOWED_FIELDS else "")

        if field in MULTI_SOURCE_ALLOWED_FIELDS:
            if isinstance(value, list):
                dedup = []
                seen = set()
                for col in value:
                    if col and col not in seen:
                        dedup.append(col)
                        seen.add(col)
                resolved[field] = dedup
            else:
                resolved[field] = []
            continue

        if not value:
            resolved[field] = ""
            continue

        if value in used_sources:
            resolved[field] = ""
        else:
            resolved[field] = value
            used_sources[value] = field

    return resolved


# =========================================================
# VALIDAÇÃO
# =========================================================

def validate_mapping(
    mapping: Dict[str, Any],
    mode: str,
) -> MappingValidation:
    mapping = clean_mapping(mapping, mode)
    required_fields = get_required_fields(mode)
    validation = MappingValidation()

    # obrigatórios
    for field in required_fields:
        value = mapping.get(field)
        if field in MULTI_SOURCE_ALLOWED_FIELDS:
            if not value:
                validation.missing_required.append(field)
        else:
            if not value:
                validation.missing_required.append(field)

    # campos inválidos
    valid_target_fields = set(get_target_fields(mode))
    for field in mapping.keys():
        if field not in valid_target_fields:
            validation.invalid_fields.append(field)

    # duplicidade
    source_usage: Dict[str, List[str]] = {}
    for field, value in mapping.items():
        if field in MULTI_SOURCE_ALLOWED_FIELDS:
            if isinstance(value, list):
                for col in value:
                    if col:
                        source_usage.setdefault(col, []).append(field)
        else:
            if value:
                source_usage.setdefault(value, []).append(field)

    for source_col, used_in in source_usage.items():
        non_image_uses = [x for x in used_in if x not in MULTI_SOURCE_ALLOWED_FIELDS]
        if len(non_image_uses) > 1:
            validation.duplicate_source_columns.append(source_col)

    # target duplicado não ocorre em dict, mas mantemos alerta lógico
    for field, value in mapping.items():
        if field in MULTI_SOURCE_ALLOWED_FIELDS and isinstance(value, list) and len(value) > 1:
            validation.warnings.append(
                f"O campo '{field}' está com múltiplas colunas de origem. Isso é permitido para imagens."
            )

    if validation.missing_required:
        validation.warnings.append(
            "Existem campos obrigatórios sem vínculo: "
            + ", ".join(validation.missing_required)
        )

    if validation.duplicate_source_columns:
        validation.warnings.append(
            "Existem colunas do fornecedor usadas em mais de um campo: "
            + ", ".join(validation.duplicate_source_columns)
        )

    if validation.invalid_fields:
        validation.warnings.append(
            "Existem campos inválidos no mapeamento: "
            + ", ".join(validation.invalid_fields)
        )

    validation.is_valid = not (
        validation.missing_required
        or validation.duplicate_source_columns
        or validation.invalid_fields
    )

    return validation


def list_unmapped_target_fields(mapping: Dict[str, Any], mode: str) -> List[str]:
    mapping = clean_mapping(mapping, mode)
    missing = []

    for field in get_target_fields(mode):
        value = mapping.get(field)
        if field in MULTI_SOURCE_ALLOWED_FIELDS:
            if not value:
                missing.append(field)
        else:
            if not value:
                missing.append(field)

    return missing


# =========================================================
# PERFIS POR FORNECEDOR
# =========================================================

def ensure_profile_dir(profile_dir: str = DEFAULT_PROFILE_DIR) -> None:
    os.makedirs(profile_dir, exist_ok=True)


def slugify_filename(value: str) -> str:
    value = normalize_text(value)
    value = value.replace(" ", "_")
    value = re.sub(r"[^a-z0-9_]", "", value)
    return value or "fornecedor"


def profile_filepath(
    supplier_name: str,
    mode: str,
    profile_dir: str = DEFAULT_PROFILE_DIR,
) -> str:
    ensure_profile_dir(profile_dir)
    file_name = f"{slugify_filename(supplier_name)}__{normalize_text(mode)}.json"
    return os.path.join(profile_dir, file_name)


def save_mapping_profile(
    supplier_name: str,
    mode: str,
    mapping: Dict[str, Any],
    profile_dir: str = DEFAULT_PROFILE_DIR,
) -> str:
    from datetime import datetime

    ensure_profile_dir(profile_dir)
    path = profile_filepath(supplier_name, mode, profile_dir)

    now_iso = datetime.now().isoformat()
    existing = load_mapping_profile(supplier_name, mode, profile_dir)

    profile = MappingProfile(
        supplier_name=supplier_name,
        mode=normalize_text(mode),
        mapping=clean_mapping(mapping, mode),
        created_at=existing.get("created_at") if existing else now_iso,
        updated_at=now_iso,
    )

    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, ensure_ascii=False, indent=2)

    return path


def load_mapping_profile(
    supplier_name: str,
    mode: str,
    profile_dir: str = DEFAULT_PROFILE_DIR,
) -> Dict[str, Any]:
    path = profile_filepath(supplier_name, mode, profile_dir)
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def delete_mapping_profile(
    supplier_name: str,
    mode: str,
    profile_dir: str = DEFAULT_PROFILE_DIR,
) -> bool:
    path = profile_filepath(supplier_name, mode, profile_dir)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def get_saved_mapping_only(
    supplier_name: str,
    mode: str,
    profile_dir: str = DEFAULT_PROFILE_DIR,
) -> Dict[str, Any]:
    profile = load_mapping_profile(supplier_name, mode, profile_dir)
    if not profile:
        return {}
    mapping = profile.get("mapping", {})
    if not isinstance(mapping, dict):
        return {}
    return mapping


# =========================================================
# FLUXO PRINCIPAL PARA O APP
# =========================================================

def build_mapping_package(
    supplier_columns: List[str],
    mode: str,
    supplier_name: Optional[str] = None,
    profile_dir: str = DEFAULT_PROFILE_DIR,
    min_score: float = 0.45,
) -> Dict[str, Any]:
    """
    Função principal para usar no app.py.

    Retorna pacote completo:
    {
        "mode": "cadastro",
        "supplier_name": "Fornecedor X",
        "target_fields": [...],
        "required_fields": [...],
        "saved_profile_found": True/False,
        "mapping": {...},
        "validation": {...},
        "unmapped_fields": [...],
        "field_candidates": {
            "codigo": [...],
            ...
        }
    }
    """
    supplier_columns = [str(c).strip() for c in supplier_columns if str(c).strip()]
    supplier_name = supplier_name or "fornecedor"

    saved_profile = get_saved_mapping_only(
        supplier_name=supplier_name,
        mode=mode,
        profile_dir=profile_dir,
    )

    mapping = suggest_mapping(
        supplier_columns=supplier_columns,
        mode=mode,
        min_score=min_score,
        existing_profile_mapping=saved_profile if saved_profile else None,
    )

    mapping = remove_duplicate_assignments(mapping, mode)
    validation = validate_mapping(mapping, mode)
    unmapped = list_unmapped_target_fields(mapping, mode)

    field_candidates: Dict[str, List[Dict[str, Any]]] = {}
    for field in get_target_fields(mode):
        field_candidates[field] = get_field_candidates(
            supplier_columns=supplier_columns,
            mode=mode,
            target_field=field,
            top_k=5,
        )

    return {
        "mode": normalize_text(mode),
        "supplier_name": supplier_name,
        "target_fields": get_target_fields(mode),
        "required_fields": get_required_fields(mode),
        "saved_profile_found": bool(saved_profile),
        "mapping": mapping,
        "validation": {
            "missing_required": validation.missing_required,
            "duplicate_source_columns": validation.duplicate_source_columns,
            "duplicate_target_fields": validation.duplicate_target_fields,
            "invalid_fields": validation.invalid_fields,
            "warnings": validation.warnings,
            "is_valid": validation.is_valid,
        },
        "unmapped_fields": unmapped,
        "field_candidates": field_candidates,
    }


def update_single_mapping(
    current_mapping: Dict[str, Any],
    mode: str,
    target_field: str,
    supplier_column: Any,
) -> Dict[str, Any]:
    """
    Atualiza um campo manualmente no app.
    - bloqueia duplicidade em campos normais
    - imagens aceitam lista ou string
    """
    mapping = clean_mapping(current_mapping, mode)

    if target_field not in get_target_fields(mode):
        return mapping

    if target_field in MULTI_SOURCE_ALLOWED_FIELDS:
        if supplier_column is None:
            mapping[target_field] = []
        elif isinstance(supplier_column, list):
            cleaned = []
            seen = set()
            for col in supplier_column:
                if col and col not in seen:
                    cleaned.append(str(col).strip())
                    seen.add(col)
            mapping[target_field] = cleaned
        elif isinstance(supplier_column, str) and supplier_column.strip():
            mapping[target_field] = [supplier_column.strip()]
        else:
            mapping[target_field] = []
        return mapping

    # remove uso duplicado da mesma source em outro campo
    supplier_column = str(supplier_column).strip() if supplier_column is not None else ""
    if supplier_column:
        for field, value in list(mapping.items()):
            if field == target_field:
                continue
            if field in MULTI_SOURCE_ALLOWED_FIELDS:
                continue
            if value == supplier_column:
                mapping[field] = ""

    mapping[target_field] = supplier_column
    return mapping


def reset_mapping(mode: str) -> Dict[str, Any]:
    mapping = {}
    for field in get_target_fields(mode):
        mapping[field] = [] if field in MULTI_SOURCE_ALLOWED_FIELDS else ""
    return mapping


# =========================================================
# UTILITÁRIOS PARA TRANSFORMAR LINHAS
# =========================================================

def extract_value_from_row(row: Dict[str, Any], source: str) -> Any:
    return row.get(source, "")


def join_multiple_values(values: List[Any], separator: str = " | ") -> str:
    clean = []
    seen = set()

    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if text not in seen:
            clean.append(text)
            seen.add(text)

    return separator.join(clean)


def apply_mapping_to_row(
    supplier_row: Dict[str, Any],
    mapping: Dict[str, Any],
    mode: str,
) -> Dict[str, Any]:
    """
    Transforma 1 linha do fornecedor em 1 linha do modelo Bling.
    """
    target_row: Dict[str, Any] = {}

    for field in get_target_fields(mode):
        source = mapping.get(field, [] if field in MULTI_SOURCE_ALLOWED_FIELDS else "")

        if field in MULTI_SOURCE_ALLOWED_FIELDS:
            values = []
            if isinstance(source, list):
                for col in source:
                    values.append(extract_value_from_row(supplier_row, col))
            elif isinstance(source, str) and source:
                values.append(extract_value_from_row(supplier_row, source))

            # Regra do projeto: imagens múltiplas separadas por |
            target_row[field] = join_multiple_values(values, separator=" | ")
        else:
            target_row[field] = extract_value_from_row(supplier_row, source) if source else ""

    return target_row


# =========================================================
# DEBUG / TESTE RÁPIDO
# =========================================================

if __name__ == "__main__":
    sample_supplier_columns = [
        "SKU",
        "Nome do Produto",
        "Marca",
        "Categoria",
        "Preço",
        "Custo",
        "EAN",
        "NCM",
        "Quantidade",
        "Imagem Principal",
        "Imagem 2",
        "Fornecedor",
        "Código do Fornecedor",
    ]

    package = build_mapping_package(
        supplier_columns=sample_supplier_columns,
        mode="cadastro",
        supplier_name="Fornecedor Exemplo",
    )

    print(json.dumps(package, ensure_ascii=False, indent=2))
