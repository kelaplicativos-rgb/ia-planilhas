from __future__ import annotations

import re

import pandas as pd


def _to_number(value: object) -> float | None:
    text = str(value or "").strip().replace("R$", "")
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return None


def apply_stock_mode(df: pd.DataFrame, mode: str = "substituir") -> pd.DataFrame:
    df = df.copy()
    if "Quantidade" not in df.columns:
        df["Quantidade"] = ""

    mode = str(mode or "substituir").lower()
    df["Modo estoque"] = mode

    if mode == "saida":
        df["Quantidade"] = df["Quantidade"].apply(lambda v: -abs(_to_number(v) or 0))
    elif mode == "entrada":
        df["Quantidade"] = df["Quantidade"].apply(lambda v: abs(_to_number(v) or 0))
    else:
        df["Quantidade"] = df["Quantidade"].apply(lambda v: _to_number(v) if _to_number(v) is not None else "")

    return df


def add_stock_delta(df: pd.DataFrame, current_col: str | None = None) -> pd.DataFrame:
    df = df.copy()
    if not current_col or current_col not in df.columns or "Quantidade" not in df.columns:
        df["Delta estoque"] = ""
        df["Alerta estoque"] = ""
        return df

    deltas = []
    alerts = []
    for _, row in df.iterrows():
        atual = _to_number(row.get(current_col))
        novo = _to_number(row.get("Quantidade"))
        if atual is None or novo is None:
            deltas.append("")
            alerts.append("sem comparação")
            continue
        delta = novo - atual
        deltas.append(delta)
        if novo < 0:
            alerts.append("estoque negativo")
        elif atual > 0 and abs(delta) / max(abs(atual), 1) >= 0.8:
            alerts.append("variação alta")
        else:
            alerts.append("")

    df["Delta estoque"] = deltas
    df["Alerta estoque"] = alerts
    return df


def stock_risk_summary(df: pd.DataFrame) -> dict[str, int]:
    summary = {"linhas": 0, "negativos": 0, "vazios": 0, "variacao_alta": 0}
    if df is None or df.empty:
        return summary
    summary["linhas"] = len(df)
    if "Quantidade" in df.columns:
        nums = df["Quantidade"].apply(_to_number)
        summary["negativos"] = int(nums.apply(lambda v: v is not None and v < 0).sum())
        summary["vazios"] = int(nums.apply(lambda v: v is None).sum())
    if "Alerta estoque" in df.columns:
        summary["variacao_alta"] = int(df["Alerta estoque"].astype(str).str.contains("variação alta", case=False, na=False).sum())
    return summary


def block_stock_export(df: pd.DataFrame) -> list[str]:
    blocks: list[str] = []
    if df is None or df.empty:
        return ["Estoque vazio."]
    if "Quantidade" not in df.columns:
        blocks.append("Coluna Quantidade ausente.")
    else:
        nums = df["Quantidade"].apply(_to_number)
        if nums.apply(lambda v: v is None).all():
            blocks.append("Nenhuma quantidade numérica válida.")
        if nums.apply(lambda v: v is not None and v < 0).any():
            blocks.append("Existem quantidades negativas. Confirme se o modo é saída/baixa.")
    if "Depósito" in df.columns and not df["Depósito"].astype(str).str.strip().any():
        blocks.append("Depósito obrigatório não informado.")
    return blocks
