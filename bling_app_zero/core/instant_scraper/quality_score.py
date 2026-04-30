from __future__ import annotations

from typing import Any

import pandas as pd


QUALITY_COLUMNS = ["_quality_score", "_quality_status", "_quality_alertas"]


def _txt(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null", "undefined"}:
        return ""
    return " ".join(text.split())


def _has_digit(value: Any) -> bool:
    return any(ch.isdigit() for ch in _txt(value))


def _looks_like_url(value: Any) -> bool:
    text = _txt(value).lower()
    return text.startswith("http://") or text.startswith("https://")


def _score_row(row: pd.Series) -> tuple[int, str, str]:
    score = 0
    alerts: list[str] = []

    nome = _txt(row.get("nome"))
    preco = _txt(row.get("preco"))
    url = _txt(row.get("url_produto"))
    imagens = _txt(row.get("imagens"))
    descricao = _txt(row.get("descricao"))
    sku = _txt(row.get("sku"))
    pid = _txt(row.get("produto_id_url"))
    marca = _txt(row.get("marca"))
    categoria = _txt(row.get("categoria"))
    gtin = _txt(row.get("gtin"))

    if nome and len(nome) >= 8:
        score += 25
    else:
        alerts.append("nome_fraco")

    if preco and _has_digit(preco):
        score += 20
    else:
        alerts.append("sem_preco")

    if _looks_like_url(url):
        score += 15
    else:
        alerts.append("sem_url_produto")

    if imagens and "http" in imagens.lower():
        score += 12
    else:
        alerts.append("sem_imagem")

    if sku or pid:
        score += 10
    else:
        alerts.append("sem_sku_ou_id")

    if descricao and len(descricao) >= 40:
        score += 8

    if marca:
        score += 4

    if categoria:
        score += 3

    if gtin:
        score += 3

    score = min(score, 100)

    if score >= 75:
        status = "bom"
    elif score >= 50:
        status = "revisar"
    else:
        status = "fraco"

    return score, status, ", ".join(alerts)


def aplicar_score_qualidade(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    result = base.apply(_score_row, axis=1)

    base["_quality_score"] = result.apply(lambda item: item[0])
    base["_quality_status"] = result.apply(lambda item: item[1])
    base["_quality_alertas"] = result.apply(lambda item: item[2])

    base = base.sort_values(by=["_quality_score"], ascending=False).reset_index(drop=True)
    return base


def remover_produtos_fracos(df: pd.DataFrame, score_minimo: int = 50) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = aplicar_score_qualidade(df)
    return base[base["_quality_score"].astype(int) >= int(score_minimo)].reset_index(drop=True)


def resumo_qualidade(df: pd.DataFrame) -> dict[str, int]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"bom": 0, "revisar": 0, "fraco": 0, "total": 0}

    base = aplicar_score_qualidade(df)
    counts = base["_quality_status"].value_counts().to_dict()
    return {
        "bom": int(counts.get("bom", 0)),
        "revisar": int(counts.get("revisar", 0)),
        "fraco": int(counts.get("fraco", 0)),
        "total": int(len(base)),
    }
