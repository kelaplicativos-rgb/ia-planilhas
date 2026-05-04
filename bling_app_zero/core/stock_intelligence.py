from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class StockColumnCandidate:
    column: str
    score: int
    reason: str
    danger: bool = False


IDENTIFIER_TARGETS = ["Código", "GTIN/EAN", "Descrição"]
STOCK_TARGETS = ["Código", "GTIN/EAN", "Descrição", "Depósito", "Quantidade"]

_IDENTIFIER_ALIASES = {
    "Código": ["codigo", "código", "cod", "sku", "referencia", "referência", "ref", "id produto", "modelo"],
    "GTIN/EAN": ["gtin", "ean", "codigo barras", "código barras", "codigo de barras", "código de barras", "barcode"],
    "Descrição": ["descricao", "descrição", "produto", "nome", "nome produto", "titulo", "título"],
}

_STOCK_ALIASES = [
    "estoque",
    "saldo",
    "quantidade",
    "qtd",
    "qtde",
    "disponivel",
    "disponível",
    "stock",
    "balance",
    "inventario",
    "inventário",
]

_DANGER_ALIASES = [
    "preco",
    "preço",
    "valor",
    "custo",
    "peso",
    "ncm",
    "ean",
    "gtin",
    "codigo barras",
    "código barras",
    "largura",
    "altura",
    "profundidade",
    "comprimento",
]


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _sample(df: pd.DataFrame, column: str, limit: int = 50) -> list[str]:
    try:
        return [str(v).strip() for v in df[column].head(limit).tolist() if str(v).strip()]
    except Exception:
        return []


def _numeric_ratio(values: list[str]) -> float:
    if not values:
        return 0.0
    total = len(values)
    numeric = 0
    for v in values:
        cleaned = str(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
        if re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
            numeric += 1
    return numeric / max(total, 1)


def _money_ratio(values: list[str]) -> float:
    if not values:
        return 0.0
    money = 0
    for v in values:
        s = str(v).strip()
        if "R$" in s or re.search(r"\d+[\.,]\d{2}$", s):
            money += 1
    return money / max(len(values), 1)


def _integerish_ratio(values: list[str]) -> float:
    if not values:
        return 0.0
    count = 0
    for v in values:
        cleaned = str(v).replace(".", "").replace(",", ".").strip()
        try:
            n = float(cleaned)
            if n.is_integer():
                count += 1
        except Exception:
            pass
    return count / max(len(values), 1)


def score_stock_quantity_column(df: pd.DataFrame, column: str) -> StockColumnCandidate:
    name = normalize_text(column)
    values = _sample(df, column)

    score = 0
    reasons: list[str] = []
    danger = False

    if any(alias in name for alias in _STOCK_ALIASES):
        score += 55
        reasons.append("nome parece estoque")

    if any(alias in name for alias in _DANGER_ALIASES):
        score -= 70
        danger = True
        reasons.append("nome perigoso para estoque")

    numeric_ratio = _numeric_ratio(values)
    integer_ratio = _integerish_ratio(values)
    money_ratio = _money_ratio(values)

    if numeric_ratio >= 0.75:
        score += 25
        reasons.append("valores numéricos")

    if integer_ratio >= 0.70:
        score += 20
        reasons.append("valores parecem quantidade inteira")

    if money_ratio >= 0.50:
        score -= 80
        danger = True
        reasons.append("parece preço/custo")

    if not values:
        score -= 30
        reasons.append("sem amostra útil")

    return StockColumnCandidate(column=str(column), score=max(0, min(100, score)), reason="; ".join(reasons) or "sem sinais fortes", danger=danger)


def detect_stock_quantity(df: pd.DataFrame) -> list[StockColumnCandidate]:
    candidates = [score_stock_quantity_column(df, str(c)) for c in df.columns]
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def detect_identifier(df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()

    for target, aliases in _IDENTIFIER_ALIASES.items():
        best_col = ""
        best_score = 0
        for col in df.columns:
            if str(col) in used:
                continue
            name = normalize_text(col)
            score = 0
            if any(normalize_text(a) == name for a in aliases):
                score += 90
            elif any(normalize_text(a) in name for a in aliases):
                score += 65

            values = _sample(df, str(col))
            if target == "GTIN/EAN":
                gtin_count = sum(1 for v in values if re.fullmatch(r"\D*\d{8,14}\D*", v))
                if values and gtin_count / len(values) >= 0.5:
                    score += 30
            if target == "Descrição":
                avg = sum(len(v) for v in values) / max(len(values), 1)
                if avg >= 8:
                    score += 20

            if score > best_score:
                best_score = score
                best_col = str(col)

        if best_col and best_score >= 60:
            mapping[target] = best_col
            used.add(best_col)

    return mapping


def build_stock_mapping(df: pd.DataFrame, deposito: str | None = None) -> dict[str, str]:
    mapping = detect_identifier(df)
    quantity_candidates = detect_stock_quantity(df)
    if quantity_candidates and quantity_candidates[0].score >= 60 and not quantity_candidates[0].danger:
        mapping["Quantidade"] = quantity_candidates[0].column
    return mapping


def build_stock_dataframe(df: pd.DataFrame, mapping: dict[str, str], deposito: str | None = None) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for target in STOCK_TARGETS:
        source = mapping.get(target, "")
        if target == "Depósito":
            out[target] = str(deposito or "").strip()
        elif source and source in df.columns:
            out[target] = df[source].astype(str).fillna("")
        else:
            out[target] = ""

    out["Quantidade"] = out["Quantidade"].astype(str).str.replace("R$", "", regex=False).str.strip()
    return out


def validate_stock_dataframe(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    if df is None or df.empty:
        return ["A atualização de estoque está vazia."]

    has_codigo = "Código" in df.columns and df["Código"].astype(str).str.strip().any()
    has_gtin = "GTIN/EAN" in df.columns and df["GTIN/EAN"].astype(str).str.strip().any()
    has_desc = "Descrição" in df.columns and df["Descrição"].astype(str).str.strip().any()

    if not (has_codigo or has_gtin or has_desc):
        warnings.append("Nenhum identificador encontrado. Use Código/SKU ou GTIN/EAN.")

    if "Quantidade" not in df.columns or not df["Quantidade"].astype(str).str.strip().any():
        warnings.append("Quantidade de estoque não encontrada.")

    if "Depósito" in df.columns and not df["Depósito"].astype(str).str.strip().any():
        warnings.append("Depósito vazio. Informe o nome do depósito antes de exportar.")

    if "Quantidade" in df.columns:
        invalid = 0
        money_like = 0
        for v in df["Quantidade"].astype(str).head(200):
            s = v.strip()
            if "R$" in s or re.search(r"\d+[\.,]\d{2}$", s):
                money_like += 1
            cleaned = s.replace(".", "").replace(",", ".")
            try:
                float(cleaned)
            except Exception:
                if s:
                    invalid += 1
        if invalid:
            warnings.append(f"Existem {invalid} quantidades não numéricas na amostra.")
        if money_like > 5:
            warnings.append("A coluna de quantidade parece conter preço/custo. Confira antes de avançar.")

    return warnings
