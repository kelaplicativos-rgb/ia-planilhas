from __future__ import annotations

import re
from typing import Any, Dict, List

import pandas as pd


def _txt(v: Any) -> str:
    if v is None:
        return ""

    s = str(v).strip()

    if s.lower() in {"none", "nan", "null"}:
        return ""

    return re.sub(r"\s+", " ", s).strip()


def _imgs(v: Any) -> str:
    if not v:
        return ""

    if isinstance(v, list):
        parts = v
    else:
        parts = str(v).replace(";", "|").replace(",", "|").split("|")

    out = []
    seen = set()

    for p in parts:
        p = _txt(p)
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)

    return "|".join(out[:12])


def normalize_products(produtos: List[Dict[str, Any]]):
    resultado = []

    for p in produtos or []:
        if not isinstance(p, dict):
            continue

        nome = _txt(p.get("nome") or p.get("Nome") or p.get("produto"))
        url = _txt(p.get("url_produto") or p.get("url") or p.get("URL"))

        if not nome and not url:
            continue

        resultado.append(
            {
                "Nome": nome,
                "Preço": p.get("preco") or p.get("Preço") or "",
                "SKU": _txt(p.get("sku") or p.get("SKU")),
                "URL": url,
                "Marca": _txt(p.get("marca") or p.get("Marca")),
                "Categoria": _txt(p.get("categoria") or p.get("Categoria")),
                "Estoque": p.get("estoque") if p.get("estoque") is not None else "",
                "GTIN": _txt(p.get("gtin") or p.get("GTIN") or p.get("EAN")),
                "Descrição": _txt(p.get("descricao") or p.get("Descrição")),
                "Imagem": _imgs(p.get("imagens") or p.get("Imagem") or p.get("Imagens")),
            }
        )

    return resultado


def to_dataframe(produtos):
    return pd.DataFrame(produtos or [])
