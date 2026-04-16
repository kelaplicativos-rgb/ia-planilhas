from __future__ import annotations

import xml.etree.ElementTree as ET
import pandas as pd


def _get_text(node, path: str) -> str:
    el = node.find(path)
    if el is not None and el.text:
        return el.text.strip()
    return ""


def parse_nfe_xml(xml_bytes: bytes) -> pd.DataFrame:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return pd.DataFrame()

    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

    itens = root.findall(".//nfe:det", ns)

    if not itens:
        return pd.DataFrame()

    rows = []

    for det in itens:
        prod = det.find(".//nfe:prod", ns)

        if prod is None:
            continue

        codigo = _get_text(prod, "nfe:cProd")
        descricao = _get_text(prod, "nfe:xProd")
        ncm = _get_text(prod, "nfe:NCM")
        cfop = _get_text(prod, "nfe:CFOP")
        unidade = _get_text(prod, "nfe:uCom")
        quantidade = _get_text(prod, "nfe:qCom")
        valor_unitario = _get_text(prod, "nfe:vUnCom")
        valor_total = _get_text(prod, "nfe:vProd")

        gtin = _get_text(prod, "nfe:cEAN")
        if gtin in {"SEM GTIN", "SEM EAN"}:
            gtin = ""

        rows.append(
            {
                "Código": codigo,
                "Descrição": descricao,
                "NCM": ncm,
                "CFOP": cfop,
                "Unidade": unidade,
                "Quantidade": quantidade,
                "Preço de custo": valor_unitario,
                "Valor total": valor_total,
                "GTIN": gtin,
            }
        )

    return pd.DataFrame(rows)
