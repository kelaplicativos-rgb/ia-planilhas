from __future__ import annotations

"""Correlação conservadora entre captação por site e modelo anexado.

Só autoaprova quando a confiança é alta e existe margem clara contra o segundo
melhor candidato. Quando há dúvida, o campo fica pendente/revisar.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Iterable, Sequence

import pandas as pd

AUTO_APPROVE_MIN_CONFIDENCE = 88
REVIEW_MIN_CONFIDENCE = 68
AMBIGUITY_MARGIN = 12


@dataclass(frozen=True)
class FieldCorrelation:
    target: str
    source: str
    confidence: int
    status: str
    reason: str
    second_source: str = ""
    second_confidence: int = 0


_TARGET_ALIASES: dict[str, tuple[str, ...]] = {
    "codigo": ("codigo", "código", "cod", "cod produto", "codigo produto", "código produto", "sku", "referencia", "referência", "ref", "modelo", "id produto"),
    "descricao": ("descricao", "descrição", "nome", "nome produto", "produto", "titulo", "título", "title", "product name", "descricao produto", "descrição produto"),
    "descricao curta": ("descricao curta", "descrição curta", "descricao", "descrição", "nome", "nome produto", "produto", "titulo", "título"),
    "descricao complementar": ("descricao complementar", "descrição complementar", "descricao completa", "descrição completa", "detalhes", "informacoes", "informações", "complemento"),
    "preco unitario": ("preco", "preço", "preco unitario", "preço unitário", "valor", "valor venda", "preco venda", "preço venda", "price", "sale price"),
    "preco de custo": ("custo", "preco custo", "preço custo", "preco de custo", "preço de custo", "valor custo", "preco compra", "preço compra", "cost"),
    "gtin ean": ("gtin", "ean", "gtin ean", "gtin/ean", "codigo barras", "código barras", "codigo de barras", "código de barras", "barcode"),
    "ncm": ("ncm", "classificacao fiscal", "classificação fiscal"),
    "marca": ("marca", "brand", "fabricante", "manufacturer"),
    "categoria": ("categoria", "category", "departamento", "grupo", "linha"),
    "departamento": ("departamento", "categoria", "category", "grupo", "linha"),
    "estoque": ("estoque", "stock", "saldo", "quantidade", "qtd", "disponivel", "disponível", "availability"),
    "quantidade": ("quantidade", "qtd", "qty", "saldo", "estoque", "stock"),
    "deposito": ("deposito", "depósito", "almoxarifado", "warehouse", "local estoque"),
    "url imagens externas": ("url imagens externas", "url imagem", "url imagens", "imagem", "imagens", "foto", "fotos", "image", "images", "picture", "gallery"),
    "link externo": ("link", "url", "url produto", "link produto", "link externo", "pagina produto", "página produto", "product url"),
    "video": ("video", "vídeo", "youtube", "url video", "url vídeo"),
    "peso bruto kg": ("peso bruto", "peso bruto kg", "peso", "weight"),
    "peso liquido kg": ("peso liquido", "peso líquido", "peso liquido kg", "peso líquido kg", "net weight"),
    "largura do produto": ("largura", "largura produto", "width"),
    "altura do produto": ("altura", "altura produto", "height"),
    "profundidade do produto": ("profundidade", "comprimento", "depth", "length"),
}

_NEGATIVE_HINTS: dict[str, tuple[str, ...]] = {
    "descricao": ("complementar", "completo", "html", "detalhe", "observacao", "observação"),
    "descricao curta": ("complementar", "completo", "html", "detalhe", "observacao", "observação"),
    "descricao complementar": ("curta", "titulo", "título", "nome"),
    "preco unitario": ("custo", "compra", "fornecedor"),
    "preco de custo": ("venda", "unitario", "unitário", "promocional", "final"),
    "url imagens externas": ("video", "vídeo", "youtube", "banner", "logo"),
    "video": ("imagem", "image", "foto"),
}

_COST_NAME_HINTS = ("custo", "compra", "fornecedor", "cost")
_SALE_PRICE_NAME_HINTS = ("preco", "preço", "valor", "venda", "unitario", "unitário", "price")
_COMPLEMENT_NAME_HINTS = ("complement", "completa", "detalhe", "informacao", "informação", "observacao", "observação")
_IMAGE_NAME_HINTS = ("imagem", "imagens", "image", "images", "foto", "fotos", "gallery", "galeria")
_VIDEO_NAME_HINTS = ("video", "vídeo", "youtube")
_REQUIRED_TARGET_HINTS = ("descricao", "descrição", "preco", "preço", "quantidade", "estoque")


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.90
    return SequenceMatcher(None, a, b).ratio()


def _canonical_target(target: object) -> str:
    norm = normalize_text(target)
    if "gtin" in norm or "ean" in norm:
        return "gtin ean"
    if "imagem" in norm or "image" in norm or "foto" in norm:
        return "url imagens externas"
    if "link" in norm or ("url" in norm and "imagem" not in norm and "image" not in norm):
        return "link externo"
    if "preco" in norm and "custo" in norm:
        return "preco de custo"
    if "preco" in norm or "valor" in norm:
        return "preco unitario"
    if "descricao" in norm and ("complement" in norm or "completa" in norm):
        return "descricao complementar"
    if "descricao" in norm and "curta" in norm:
        return "descricao curta"
    if norm in _TARGET_ALIASES:
        return norm

    best_key = norm
    best_score = 0.0
    for key, aliases in _TARGET_ALIASES.items():
        for alias in aliases + (key,):
            score = _similarity(norm, normalize_text(alias))
            if score > best_score:
                best_key = key
                best_score = score
    return best_key if best_score >= 0.78 else norm


def _clean_model_columns(columns: Sequence[object]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for col in columns:
        name = str(col or "").replace("\ufeff", "").strip().strip('"')
        if not name:
            continue
        key = normalize_text(name)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(name)
    return cleaned


def _sample_values(df: pd.DataFrame, column: str, limit: int = 35) -> list[str]:
    try:
        values = df[column].head(limit).tolist()
    except Exception:
        return []
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in {"nan", "none", "null"}:
            out.append(text)
    return out


def _content_score(canonical: str, values: Iterable[str]) -> tuple[int, str]:
    vals = list(values)
    if not vals:
        return 0, "sem amostra"
    numeric = sum(1 for v in vals if re.search(r"\d", v))
    money = sum(1 for v in vals if re.search(r"(?:r\$\s*)?\d+[\.,]\d{2}", v.lower()))
    urls = sum(1 for v in vals if "http://" in v.lower() or "https://" in v.lower() or "www." in v.lower())
    gtin = sum(1 for v in vals if re.fullmatch(r"\D*\d{8,14}\D*", v.strip()))
    ncm = sum(1 for v in vals if re.fullmatch(r"\D*\d{8}\D*", v.strip()))
    avg_len = sum(len(v) for v in vals) / max(len(vals), 1)

    if canonical in {"preco unitario", "preco de custo"}:
        return min(34, money * 7 + numeric * 2), f"preço/número detectado ({money}/{numeric})"
    if canonical in {"estoque", "quantidade"}:
        return min(30, numeric * 4), f"quantidade numérica ({numeric})"
    if canonical == "gtin ean":
        return min(42, gtin * 11), f"GTIN/EAN compatível ({gtin})"
    if canonical == "ncm":
        return min(35, ncm * 12), f"NCM 8 dígitos ({ncm})"
    if canonical == "url imagens externas":
        return min(45, urls * 12), f"URL de imagem/link detectada ({urls})"
    if canonical == "link externo":
        return min(35, urls * 10), f"URL de produto detectada ({urls})"
    if canonical in {"descricao", "descricao curta"}:
        return (28 if avg_len >= 8 else 8), f"texto médio {avg_len:.0f} caracteres"
    if canonical == "descricao complementar":
        return (30 if avg_len >= 28 else 6), f"texto complementar médio {avg_len:.0f} caracteres"
    if canonical in {"marca", "categoria", "departamento"}:
        return (18 if avg_len <= 45 and numeric < len(vals) else 4), "texto categórico provável"
    return 0, "sem regra específica"


def _name_score(canonical: str, source_col: object) -> tuple[int, str]:
    src = normalize_text(source_col)
    aliases = tuple(normalize_text(a) for a in _TARGET_ALIASES.get(canonical, (canonical,))) + (normalize_text(canonical),)
    best_alias = ""
    best = 0
    for alias in aliases:
        score = int(round(_similarity(src, alias) * 66))
        if score > best:
            best = score
            best_alias = alias
    return best, best_alias


def _negative_penalty(canonical: str, source_col: object) -> int:
    src = normalize_text(source_col)
    penalty = 0
    for hint in _NEGATIVE_HINTS.get(canonical, ()): 
        if normalize_text(hint) in src:
            penalty += 32
    return penalty


def _strict_domain_penalty(canonical: str, source_col: object) -> tuple[int, str]:
    src = normalize_text(source_col)
    penalty = 0
    reasons: list[str] = []

    if canonical == "preco de custo" and not any(hint in src for hint in _COST_NAME_HINTS):
        penalty += 45
        reasons.append("custo exige nome com custo/compra/fornecedor")

    if canonical == "preco unitario" and any(hint in src for hint in _COST_NAME_HINTS):
        penalty += 45
        reasons.append("preço de venda não deve usar custo/compra")

    if canonical == "descricao complementar" and not any(hint in src for hint in _COMPLEMENT_NAME_HINTS):
        penalty += 35
        reasons.append("descrição complementar exige pista de complemento/detalhe")

    if canonical in {"descricao", "descricao curta"} and any(hint in src for hint in _COMPLEMENT_NAME_HINTS):
        penalty += 35
        reasons.append("descrição principal não deve usar complemento/detalhe")

    if canonical == "url imagens externas" and any(hint in src for hint in _VIDEO_NAME_HINTS):
        penalty += 50
        reasons.append("imagem não deve usar coluna de vídeo")

    if canonical == "video" and any(hint in src for hint in _IMAGE_NAME_HINTS):
        penalty += 50
        reasons.append("vídeo não deve usar coluna de imagem")

    return penalty, "; ".join(reasons)


def _score_pair(target: str, source_col: str, df: pd.DataFrame) -> tuple[int, str]:
    canonical = _canonical_target(target)
    name_points, alias = _name_score(canonical, source_col)
    content_points, content_reason = _content_score(canonical, _sample_values(df, source_col))
    penalty = _negative_penalty(canonical, source_col)
    strict_penalty, strict_reason = _strict_domain_penalty(canonical, source_col)
    score = max(0, min(100, name_points + content_points - penalty - strict_penalty))
    reason = f"{canonical}; nome≈{alias or '-'}={name_points}; conteúdo={content_points} ({content_reason})"
    if penalty:
        reason += f"; penalidade={penalty}"
    if strict_penalty:
        reason += f"; trava={strict_penalty} ({strict_reason})"
    return score, reason


def _is_required_target(target: str) -> bool:
    norm = normalize_text(target)
    return any(hint in norm for hint in _REQUIRED_TARGET_HINTS)


def correlate_model_fields(
    df_source: pd.DataFrame,
    model_columns: Sequence[object],
    *,
    min_auto_confidence: int = AUTO_APPROVE_MIN_CONFIDENCE,
    min_review_confidence: int = REVIEW_MIN_CONFIDENCE,
    ambiguity_margin: int = AMBIGUITY_MARGIN,
    learned_mapping: dict[str, str] | None = None,
) -> list[FieldCorrelation]:
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        return []

    targets = _clean_model_columns(model_columns)
    learned_mapping = learned_mapping or {}
    used_sources: set[str] = set()
    output: list[FieldCorrelation] = []

    for target in targets:
        learned_source = learned_mapping.get(target)
        if learned_source and learned_source in df_source.columns and learned_source not in used_sources:
            used_sources.add(str(learned_source))
            output.append(FieldCorrelation(target, str(learned_source), 99, "auto_aprovado", "mapeamento aprendido e coluna ainda existe"))
            continue

        candidates: list[tuple[int, str, str]] = []
        for source_col in df_source.columns:
            if str(source_col) in used_sources:
                continue
            score, reason = _score_pair(target, str(source_col), df_source)
            candidates.append((score, str(source_col), reason))

        candidates.sort(key=lambda item: item[0], reverse=True)
        if not candidates:
            output.append(FieldCorrelation(target, "", 0, "pendente", "sem colunas de origem disponíveis"))
            continue

        best_score, best_source, best_reason = candidates[0]
        second_score, second_source = (candidates[1][0], candidates[1][1]) if len(candidates) > 1 else (0, "")
        margin = best_score - second_score

        if best_score >= min_auto_confidence and margin >= ambiguity_margin:
            status = "auto_aprovado"
            used_sources.add(best_source)
        elif best_score >= min_review_confidence:
            status = "revisar"
        else:
            status = "obrigatorio" if _is_required_target(target) else "pendente"
            best_source = ""

        reason = best_reason + f"; margem={margin}; segundo={second_source or '-'}:{second_score}"
        output.append(FieldCorrelation(target, best_source, best_score, status, reason, second_source, second_score))

    return output


def mapping_from_correlations(correlations: Sequence[FieldCorrelation], *, only_auto: bool = True) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used_sources: set[str] = set()
    for item in correlations:
        if not item.source:
            continue
        if only_auto and item.status != "auto_aprovado":
            continue
        if item.source in used_sources:
            continue
        used_sources.add(item.source)
        mapping[item.target] = item.source
    return mapping


def build_correlated_dataframe(
    df_source: pd.DataFrame,
    model_columns: Sequence[object],
    correlations: Sequence[FieldCorrelation],
    *,
    deposito: str | None = None,
    include_review_suggestions: bool = False,
) -> pd.DataFrame:
    targets = _clean_model_columns(model_columns)
    mapping = mapping_from_correlations(correlations, only_auto=not include_review_suggestions)
    out = pd.DataFrame(index=df_source.index)

    for target in targets:
        source = mapping.get(target, "")
        if source and source in df_source.columns:
            out[target] = df_source[source].astype(str).fillna("")
        else:
            out[target] = ""

    if deposito:
        for col in out.columns:
            if normalize_text(col) == "deposito":
                out[col] = deposito
    return out.fillna("")


def correlations_to_dataframe(correlations: Sequence[FieldCorrelation]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Campo modelo": item.target,
            "Coluna origem": item.source,
            "Confiança": item.confidence,
            "Status": item.status,
            "Segundo candidato": item.second_source,
            "Confiança 2º": item.second_confidence,
            "Motivo": item.reason,
        }
        for item in correlations
    ])
