from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class StockAiSummary:
    linhas: int
    ruptura: int
    baixo: int
    excesso: int
    ok: int


def _normalize(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _to_number(value: object) -> float | None:
    text = str(value or "").strip().replace("R$", "")
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def detect_sales_column(df: pd.DataFrame) -> str:
    aliases = [
        "venda",
        "vendas",
        "vendido",
        "giro",
        "media venda",
        "média venda",
        "saida media",
        "saída média",
        "consumo",
        "demanda",
    ]

    best_col = ""
    best_score = 0

    for col in df.columns:
        name = _normalize(col)
        score = 0
        if any(a == name for a in aliases):
            score += 90
        elif any(a in name for a in aliases):
            score += 60

        values = [str(v).strip() for v in df[col].head(50).tolist() if str(v).strip()]
        numeric = 0
        for v in values:
            if _to_number(v) is not None:
                numeric += 1
        if values and numeric / len(values) >= 0.7:
            score += 20

        if score > best_score:
            best_score = score
            best_col = str(col)

    return best_col if best_score >= 60 else ""


def apply_stock_ai(df: pd.DataFrame, sales_col: str | None = None, min_days: int = 7, target_days: int = 30) -> pd.DataFrame:
    df = df.copy()

    if "Quantidade" not in df.columns:
        df["Quantidade"] = ""

    sales_col = sales_col or detect_sales_column(df)

    status_list: list[str] = []
    suggestion_list: list[str] = []
    days_list: list[str | float] = []
    reorder_list: list[str | float] = []

    for _, row in df.iterrows():
        qty = _to_number(row.get("Quantidade"))
        sales = _to_number(row.get(sales_col)) if sales_col and sales_col in df.columns else None

        if qty is None:
            status_list.append("sem quantidade")
            suggestion_list.append("corrigir quantidade")
            days_list.append("")
            reorder_list.append("")
            continue

        if qty <= 0:
            status_list.append("ruptura")
            suggestion_list.append("repor urgente")
            days_list.append(0)
            reorder_list.append(max(1, int((sales or 1) * target_days)))
            continue

        if sales and sales > 0:
            days = round(qty / sales, 1)
            days_list.append(days)
            if days < min_days:
                status_list.append("baixo")
                needed = max(0, int((sales * target_days) - qty))
                suggestion_list.append("repor")
                reorder_list.append(needed)
            elif days > target_days * 3:
                status_list.append("excesso")
                suggestion_list.append("reduzir compra")
                reorder_list.append(0)
            else:
                status_list.append("ok")
                suggestion_list.append("manter")
                reorder_list.append(0)
        else:
            days_list.append("")
            if qty <= 2:
                status_list.append("baixo")
                suggestion_list.append("revisar reposição")
                reorder_list.append("")
            elif qty >= 100:
                status_list.append("excesso")
                suggestion_list.append("verificar giro")
                reorder_list.append(0)
            else:
                status_list.append("ok")
                suggestion_list.append("manter")
                reorder_list.append(0)

    df["Status AI estoque"] = status_list
    df["Sugestão AI estoque"] = suggestion_list
    df["Cobertura dias"] = days_list
    df["Reposição sugerida"] = reorder_list

    return df


def summarize_stock_ai(df: pd.DataFrame) -> StockAiSummary:
    if df is None or df.empty or "Status AI estoque" not in df.columns:
        return StockAiSummary(0, 0, 0, 0, 0)

    s = df["Status AI estoque"].astype(str).str.lower()
    return StockAiSummary(
        linhas=len(df),
        ruptura=int((s == "ruptura").sum()),
        baixo=int((s == "baixo").sum()),
        excesso=int((s == "excesso").sum()),
        ok=int((s == "ok").sum()),
    )
