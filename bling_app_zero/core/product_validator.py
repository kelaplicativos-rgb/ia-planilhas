from __future__ import annotations

from typing import List

import pandas as pd

from bling_app_zero.rules.gtin_rules import is_valid_gtin
from bling_app_zero.rules.price_rules import to_float


def validate_product_master(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return df

    out = df.copy()
    if "status_validacao" not in out.columns:
        out["status_validacao"] = "pendente"
    if "alertas_validacao" not in out.columns:
        out["alertas_validacao"] = ""

    for idx, row in out.iterrows():
        alerts: List[str] = []

        descricao = str(row.get("descricao", "") or "").strip()
        preco = to_float(row.get("preco_venda", 0), 0.0)
        gtin = str(row.get("gtin", "") or "").strip()

        if not descricao:
            alerts.append("sem descrição")
        if preco <= 0:
            alerts.append("sem preço válido")
        if gtin and not is_valid_gtin(gtin):
            alerts.append("GTIN inválido")

        out.at[idx, "alertas_validacao"] = " | ".join(alerts)
        out.at[idx, "status_validacao"] = "ok" if not alerts else "revisar"

    return out


def get_validation_summary(df: pd.DataFrame) -> dict:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {
            "total": 0,
            "ok": 0,
            "revisar": 0,
            "sem_descricao": 0,
            "sem_preco": 0,
            "gtin_invalidos": 0,
        }

    safe = validate_product_master(df)
    alerts = safe.get("alertas_validacao", pd.Series(dtype=str)).fillna("").astype(str)
    return {
        "total": int(len(safe)),
        "ok": int((safe.get("status_validacao") == "ok").sum()),
        "revisar": int((safe.get("status_validacao") == "revisar").sum()),
        "sem_descricao": int(alerts.str.contains("sem descrição", case=False, regex=False).sum()),
        "sem_preco": int(alerts.str.contains("sem preço válido", case=False, regex=False).sum()),
        "gtin_invalidos": int(alerts.str.contains("GTIN inválido", case=False, regex=False).sum()),
    }
