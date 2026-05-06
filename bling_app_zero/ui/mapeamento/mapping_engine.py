from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MappingAnalysisResult:
    campo: str
    coluna: str
    confidence: float
    status: str
    detected_type: str
    sample_value: str
    reason: str
    valid: bool
    color: str


def _norm(texto: Any) -> str:
    raw = str(texto or "").strip().lower()
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", raw).strip()


def _digits(valor: Any) -> str:
    return re.sub(r"\D+", "", str(valor or ""))


def _sample_values(df: pd.DataFrame, coluna: str, limit: int = 30) -> list[str]:
    if not isinstance(df, pd.DataFrame) or coluna not in df.columns:
        return []
    valores: list[str] = []
    for valor in df[coluna].dropna().astype(str).tolist():
        texto = valor.strip()
        if texto and texto.lower() not in {"nan", "none", "null"}:
            valores.append(texto)
        if len(valores) >= limit:
            break
    return valores


def _parse_number(valor: Any) -> float | None:
    texto = str(valor or "").strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").replace("r$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")
    texto = re.sub(r"[^0-9.\-]", "", texto)
    if not texto or texto in {"-", "."}:
        return None
    try:
        return float(texto)
    except Exception:
        return None


def _ratio(samples: list[str], predicate) -> float:
    if not samples:
        return 0.0
    ok = sum(1 for item in samples if predicate(item))
    return ok / max(1, len(samples))


def _field_kind(campo: str) -> str:
    nome = _norm(campo)
    if any(t in nome for t in ["gtin", "ean", "codigo de barras", "barcode"]):
        return "gtin"
    if "ncm" in nome:
        return "ncm"
    if any(t in nome for t in ["preco", "valor", "unitario", "venda"]):
        return "preco"
    if any(t in nome for t in ["estoque", "quantidade", "saldo", "balanco", "balanco"]):
        return "estoque"
    if any(t in nome for t in ["descricao", "produto", "nome", "titulo"]):
        if "complement" in nome:
            return "descricao_complementar"
        return "descricao"
    if any(t in nome for t in ["imagem", "image", "foto", "url"]):
        return "imagem"
    if any(t in nome for t in ["categoria", "category", "breadcrumb"]):
        return "categoria"
    if any(t in nome for t in ["codigo", "sku", "referencia", "id"]):
        return "codigo"
    return "generico"


def _column_name_bonus(campo: str, coluna: str, kind: str) -> float:
    c = _norm(campo)
    o = _norm(coluna)
    if not o:
        return 0.0
    if c == o:
        return 0.25
    bonus = 0.0
    aliases = {
        "gtin": ["gtin", "ean", "codigo de barras", "barcode"],
        "ncm": ["ncm"],
        "preco": ["preco", "valor", "price", "venda", "unitario"],
        "estoque": ["estoque", "quantidade", "saldo", "stock", "balanco"],
        "descricao": ["descricao", "nome", "produto", "titulo", "title"],
        "codigo": ["codigo", "sku", "referencia", "ref", "id"],
        "imagem": ["imagem", "image", "foto", "url"],
        "categoria": ["categoria", "category", "breadcrumb"],
    }
    for token in aliases.get(kind, []):
        if token in o:
            bonus = max(bonus, 0.20)
    if any(part and part in o for part in c.split()):
        bonus = max(bonus, 0.12)
    return bonus


def infer_column_type(samples: list[str], coluna: str = "") -> str:
    nome = _norm(coluna)
    gtin_ratio = _ratio(samples, lambda v: len(_digits(v)) in {8, 12, 13, 14} and _digits(v) == re.sub(r"\D+", "", v))
    ncm_ratio = _ratio(samples, lambda v: len(_digits(v)) == 8)
    price_ratio = _ratio(samples, lambda v: (_parse_number(v) is not None and _parse_number(v) > 0))
    int_ratio = _ratio(samples, lambda v: (_parse_number(v) is not None and float(_parse_number(v)).is_integer()))
    url_ratio = _ratio(samples, lambda v: str(v).strip().lower().startswith(("http://", "https://")))
    text_ratio = _ratio(samples, lambda v: len(str(v).strip()) >= 8 and bool(re.search(r"[A-Za-zÀ-ÿ]", str(v))))

    if "gtin" in nome or "ean" in nome or "barcode" in nome:
        if gtin_ratio >= 0.50:
            return "gtin"
    if "ncm" in nome and ncm_ratio >= 0.50:
        return "ncm"
    if url_ratio >= 0.50:
        return "imagem_url"
    if gtin_ratio >= 0.70:
        return "gtin"
    if ncm_ratio >= 0.80 and "ncm" in nome:
        return "ncm"
    if price_ratio >= 0.60 and any(t in nome for t in ["preco", "valor", "price", "venda"]):
        return "preco"
    if int_ratio >= 0.70 and any(t in nome for t in ["estoque", "quantidade", "saldo", "stock"]):
        return "estoque"
    if any(t in nome for t in ["codigo", "sku", "referencia", "ref", "id"]):
        return "sku_codigo"
    if text_ratio >= 0.55:
        return "texto"
    if price_ratio >= 0.70:
        return "numero"
    return "desconhecido"


def analyze_mapping(df_origem: pd.DataFrame, campo_bling: str, coluna_origem: str) -> MappingAnalysisResult:
    campo = str(campo_bling or "").strip()
    coluna = str(coluna_origem or "").strip()
    if not coluna:
        return MappingAnalysisResult(campo, coluna, 0.0, "pending", "vazio", "", "Escolha uma coluna da origem.", False, "red")
    if not isinstance(df_origem, pd.DataFrame) or coluna not in df_origem.columns:
        return MappingAnalysisResult(campo, coluna, 0.0, "invalid", "erro", "", "Coluna não encontrada na origem.", False, "red")

    samples = _sample_values(df_origem, coluna)
    sample = samples[0] if samples else ""
    kind = _field_kind(campo)
    detected = infer_column_type(samples, coluna)
    name_bonus = _column_name_bonus(campo, coluna, kind)

    gtin_ratio = _ratio(samples, lambda v: len(_digits(v)) in {8, 12, 13, 14})
    ncm_ratio = _ratio(samples, lambda v: len(_digits(v)) == 8)
    price_ratio = _ratio(samples, lambda v: (_parse_number(v) is not None and _parse_number(v) > 0))
    stock_ratio = _ratio(samples, lambda v: (_parse_number(v) is not None and _parse_number(v) >= 0))
    url_ratio = _ratio(samples, lambda v: str(v).strip().lower().startswith(("http://", "https://")))
    text_ratio = _ratio(samples, lambda v: len(str(v).strip()) >= 8 and bool(re.search(r"[A-Za-zÀ-ÿ]", str(v))))

    confidence = 0.15 + name_bonus
    status = "warning"
    valid = False
    reason = "Compatibilidade incerta. Confira a amostra antes de seguir."

    if kind == "gtin":
        confidence = min(1.0, gtin_ratio * 0.75 + name_bonus)
        valid = gtin_ratio >= 0.60
        status = "valid" if valid else "invalid"
        reason = "GTIN válido: maioria das amostras tem 8, 12, 13 ou 14 dígitos." if valid else "Inválido para GTIN/EAN: precisa ter 8, 12, 13 ou 14 dígitos."
    elif kind == "ncm":
        confidence = min(1.0, ncm_ratio * 0.78 + name_bonus)
        valid = ncm_ratio >= 0.60
        status = "valid" if valid else "invalid"
        reason = "NCM compatível: amostras com 8 dígitos." if valid else "Inválido para NCM: precisa ter exatamente 8 dígitos."
    elif kind == "preco":
        confidence = min(1.0, price_ratio * 0.75 + name_bonus)
        valid = price_ratio >= 0.50
        status = "valid" if confidence >= 0.70 else ("warning" if valid else "invalid")
        reason = "Preço compatível: valores monetários/números positivos detectados." if valid else "Inválido para preço: não encontrei valores monetários/números positivos suficientes."
    elif kind == "estoque":
        confidence = min(1.0, stock_ratio * 0.68 + name_bonus)
        valid = stock_ratio >= 0.55
        status = "valid" if confidence >= 0.70 else ("warning" if valid else "invalid")
        reason = "Estoque compatível: quantidades numéricas detectadas." if valid else "Inválido para estoque: não encontrei quantidades numéricas suficientes."
    elif kind in {"descricao", "descricao_complementar"}:
        confidence = min(1.0, text_ratio * 0.70 + name_bonus)
        valid = text_ratio >= 0.45
        status = "valid" if confidence >= 0.65 else ("warning" if valid else "invalid")
        reason = "Texto de produto detectado." if valid else "Inválido para descrição: amostra não parece texto de produto."
    elif kind == "codigo":
        sku_like = detected in {"sku_codigo", "numero", "texto"} and gtin_ratio < 0.70
        confidence = min(1.0, (0.65 if sku_like else 0.25) + name_bonus)
        valid = sku_like
        status = "valid" if confidence >= 0.60 else "warning"
        reason = "Código/SKU compatível. Não será tratado como GTIN sem validação própria." if valid else "Código incerto: confira se é SKU, ID ou referência."
    elif kind == "imagem":
        confidence = min(1.0, url_ratio * 0.75 + name_bonus)
        valid = url_ratio >= 0.45
        status = "valid" if valid else "warning"
        reason = "URLs de imagem/link detectadas." if valid else "Não identifiquei URLs suficientes nesta coluna."
    elif kind == "categoria":
        confidence = min(1.0, text_ratio * 0.55 + name_bonus)
        valid = text_ratio >= 0.35
        status = "valid" if confidence >= 0.55 else "warning"
        reason = "Texto de categoria/breadcrumb detectado." if valid else "Categoria incerta. Confira a amostra."
    else:
        confidence = min(1.0, 0.35 + name_bonus)
        valid = bool(samples)
        status = "warning" if valid else "invalid"

    if status == "valid":
        color = "green"
    elif status == "warning":
        color = "yellow"
    else:
        color = "red"

    return MappingAnalysisResult(campo, coluna, round(float(confidence), 2), status, detected, sample, reason, valid, color)


def render_mapping_feedback(result: MappingAnalysisResult) -> None:
    import streamlit as st

    pct = int(round(result.confidence * 100))
    texto = (
        f"Campo Bling: {result.campo} | Coluna origem: {result.coluna or '-'} | "
        f"Amostra: {result.sample_value or '-'} | Tipo provável: {result.detected_type} | Confiança: {pct}% | {result.reason}"
    )
    if result.status == "valid":
        st.success(texto)
    elif result.status == "warning":
        st.warning(texto)
    elif result.status == "pending":
        st.caption(texto)
    else:
        st.error(texto)


def log_mapping_analysis(result: MappingAnalysisResult) -> None:
    try:
        import streamlit as st
        linha = (
            f"[MAPPING] campo={result.campo} coluna={result.coluna} "
            f"sample={result.sample_value} detected_type={result.detected_type} "
            f"confidence={result.confidence} status={result.status} reason={result.reason}"
        )
        logs = st.session_state.setdefault("logs", [])
        if not logs or logs[-1] != linha:
            logs.append(linha)
    except Exception:
        return
