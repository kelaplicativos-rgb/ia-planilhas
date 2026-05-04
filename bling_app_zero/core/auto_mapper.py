from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Sequence

import pandas as pd


@dataclass(frozen=True)
class MappingSuggestion:
    target: str
    source: str
    confidence: int
    reason: str


BLING_CADASTRO_COLUMNS = [
    "Código",
    "Descrição",
    "Descrição complementar",
    "Unidade",
    "NCM",
    "GTIN/EAN",
    "Preço unitário",
    "Preço de custo",
    "Marca",
    "Categoria",
    "Peso bruto (Kg)",
    "Peso líquido (Kg)",
    "Largura do produto",
    "Altura do produto",
    "Profundidade do produto",
    "URL imagens externas",
    "Estoque",
]

BLING_ESTOQUE_COLUMNS = [
    "Código",
    "GTIN/EAN",
    "Descrição",
    "Depósito",
    "Estoque",
    "Quantidade",
]

_FIELD_ALIASES: dict[str, list[str]] = {
    "Código": ["codigo", "cod", "cod produto", "codigo produto", "sku", "id produto", "referencia", "ref", "modelo", "cod fornecedor"],
    "Descrição": ["descricao", "descrição", "produto", "nome", "nome produto", "titulo", "title", "description", "product name"],
    "Descrição complementar": ["descricao complementar", "descrição complementar", "descricao completa", "detalhes", "observacao", "observacoes", "complemento", "informacoes"],
    "Unidade": ["unidade", "un", "und", "medida", "unit"],
    "NCM": ["ncm", "classificacao fiscal", "classificação fiscal"],
    "GTIN/EAN": ["gtin", "ean", "codigo barras", "código barras", "codigo de barras", "código de barras", "barcode"],
    "Preço unitário": ["preco", "preço", "valor", "valor venda", "preco venda", "preço venda", "preco unitario", "preço unitário", "price", "sale price"],
    "Preço de custo": ["custo", "preco custo", "preço custo", "valor custo", "cost", "preco compra", "preço compra"],
    "Marca": ["marca", "brand", "fabricante", "manufacturer"],
    "Categoria": ["categoria", "category", "departamento", "grupo", "linha"],
    "Peso bruto (Kg)": ["peso bruto", "peso", "weight", "peso kg", "peso bruto kg"],
    "Peso líquido (Kg)": ["peso liquido", "peso líquido", "net weight", "peso liquido kg"],
    "Largura do produto": ["largura", "width", "largura produto"],
    "Altura do produto": ["altura", "height", "altura produto"],
    "Profundidade do produto": ["profundidade", "comprimento", "depth", "length"],
    "URL imagens externas": ["imagem", "imagens", "url imagem", "url imagens", "image", "images", "foto", "fotos", "picture"],
    "Estoque": ["estoque", "stock", "saldo", "quantidade", "qtd", "disponivel", "disponível"],
    "Quantidade": ["quantidade", "qtd", "qty", "saldo", "estoque", "stock"],
    "Depósito": ["deposito", "depósito", "almoxarifado", "warehouse", "local estoque"],
}

_NEGATIVE_HINTS: dict[str, list[str]] = {
    "Descrição": ["complementar", "complemento", "observacao", "observações", "html", "detalhe"],
    "Descrição complementar": ["curta", "resumo"],
    "URL imagens externas": ["video", "vídeo", "youtube", "propaganda", "banner"],
}


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def supplier_signature(df: pd.DataFrame) -> str:
    cols = "|".join(normalize_text(c) for c in df.columns)
    return hashlib.sha1(cols.encode("utf-8")).hexdigest()[:12]


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.88
    return SequenceMatcher(None, a, b).ratio()


def _sample_values(df: pd.DataFrame, column: str, limit: int = 30) -> list[str]:
    try:
        return [str(v).strip() for v in df[column].head(limit).tolist() if str(v).strip()]
    except Exception:
        return []


def _canonical_target(target: str) -> str:
    normalized = normalize_text(target)
    all_targets = BLING_CADASTRO_COLUMNS + BLING_ESTOQUE_COLUMNS
    best = target
    best_score = 0.0
    for candidate in all_targets:
        score = _similarity(normalized, normalize_text(candidate))
        if score > best_score:
            best = candidate
            best_score = score
    return best if best_score >= 0.72 else target


def _content_score(target: str, values: Iterable[str]) -> int:
    canonical = _canonical_target(target)
    vals = list(values)
    if not vals:
        return 0
    joined = " ".join(vals[:20]).lower()
    numeric_count = sum(1 for v in vals if re.search(r"\d", v))
    url_count = sum(1 for v in vals if "http://" in v.lower() or "https://" in v.lower())
    money_like = sum(1 for v in vals if re.search(r"\d+[\.,]\d{2}", v))
    gtin_like = sum(1 for v in vals if re.fullmatch(r"\D*\d{8,14}\D*", v.strip()))

    if canonical in {"Preço unitário", "Preço de custo"}:
        return min(30, money_like * 6 + numeric_count * 2)
    if canonical in {"Estoque", "Quantidade"}:
        return min(25, numeric_count * 3)
    if canonical == "GTIN/EAN":
        return min(40, gtin_like * 10)
    if canonical == "URL imagens externas":
        return min(45, url_count * 12)
    if canonical == "NCM":
        return 25 if re.search(r"\b\d{8}\b", joined) else 0
    if canonical == "Descrição":
        avg_len = sum(len(v) for v in vals) / max(len(vals), 1)
        return 25 if avg_len >= 8 else 5
    if canonical == "Descrição complementar":
        avg_len = sum(len(v) for v in vals) / max(len(vals), 1)
        return 25 if avg_len >= 30 else 0
    return 0


def _score_column(target: str, source_col: str, df: pd.DataFrame) -> tuple[int, str]:
    normalized_col = normalize_text(source_col)
    canonical = _canonical_target(target)
    aliases = [normalize_text(a) for a in _FIELD_ALIASES.get(canonical, [target, canonical])]
    aliases.append(normalize_text(target))

    best_alias = ""
    best_name_score = 0
    for alias in aliases:
        score = int(round(_similarity(normalized_col, alias) * 70))
        if score > best_name_score:
            best_name_score = score
            best_alias = alias

    penalty = 0
    for negative in _NEGATIVE_HINTS.get(canonical, []):
        neg = normalize_text(negative)
        if neg and neg in normalized_col:
            penalty += 35

    content = _content_score(canonical, _sample_values(df, source_col))
    final = max(0, min(100, best_name_score + content - penalty))
    reason = f"alvo={canonical}; nome≈{best_alias or target}; conteúdo={content}"
    if penalty:
        reason += f"; penalidade={penalty}"
    return final, reason


def _clean_target_columns(columns: Sequence[object]) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for col in columns:
        name = str(col or "").replace("\ufeff", "").strip().strip('"')
        if not name:
            continue
        normalized = normalize_text(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        targets.append(name)
    return targets


def get_bling_columns(tipo_operacao: str | None = None, modelo_columns: Sequence[object] | None = None) -> list[str]:
    from_modelo = _clean_target_columns(modelo_columns or [])
    if from_modelo:
        return from_modelo

    tipo = normalize_text(tipo_operacao)
    if "estoque" in tipo:
        return BLING_ESTOQUE_COLUMNS.copy()
    return BLING_CADASTRO_COLUMNS.copy()


def suggest_mapping(
    df: pd.DataFrame,
    tipo_operacao: str | None = None,
    min_confidence: int = 55,
    learned_mapping: dict[str, str] | None = None,
    modelo_columns: Sequence[object] | None = None,
) -> list[MappingSuggestion]:
    if df is None or df.empty:
        return []

    targets = get_bling_columns(tipo_operacao, modelo_columns=modelo_columns)
    used_sources: set[str] = set()
    suggestions: list[MappingSuggestion] = []
    learned_mapping = learned_mapping or {}

    for target in targets:
        learned_source = learned_mapping.get(target)
        if learned_source and learned_source in df.columns and learned_source not in used_sources:
            used_sources.add(learned_source)
            suggestions.append(MappingSuggestion(target, learned_source, 99, "aprendido com revisão anterior"))
            continue

        candidates: list[tuple[int, str, str]] = []
        for source_col in df.columns:
            if source_col in used_sources:
                continue
            score, reason = _score_column(target, str(source_col), df)
            candidates.append((score, str(source_col), reason))

        candidates.sort(key=lambda item: item[0], reverse=True)
        if candidates and candidates[0][0] >= min_confidence:
            confidence, source, reason = candidates[0]
            used_sources.add(source)
            suggestions.append(MappingSuggestion(target, source, confidence, reason))

    return suggestions


def build_mapped_dataframe(
    df: pd.DataFrame,
    mapping: dict[str, str],
    tipo_operacao: str | None = None,
    deposito: str | None = None,
    modelo_columns: Sequence[object] | None = None,
) -> pd.DataFrame:
    targets = get_bling_columns(tipo_operacao, modelo_columns=modelo_columns)
    out = pd.DataFrame(index=df.index)
    for target in targets:
        source = mapping.get(target, "")
        if source and source in df.columns:
            out[target] = df[source].astype(str).fillna("")
        else:
            out[target] = ""
    if deposito:
        for col in out.columns:
            if normalize_text(col) == "deposito":
                out[col] = deposito
    return out
