
from __future__ import annotations

import xml.etree.ElementTree as ET
import pandas as pd


# ============================================================
# HELPERS
# ============================================================

def _safe_str(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _remover_namespace(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _to_float(valor: str) -> float:
    if not valor:
        return 0.0
    valor = valor.replace(",", ".")
    try:
        return float(valor)
    except Exception:
        return 0.0


def _formatar_preco(valor: str) -> str:
    return f"{_to_float(valor):.2f}".replace(".", ",")


# ============================================================
# EXTRAÇÃO XML NFE
# ============================================================

def converter_upload_xml_para_dataframe(upload) -> pd.DataFrame:
    try:
        bruto = upload.getvalue()
        root = ET.fromstring(bruto)
    except Exception:
        return pd.DataFrame()

    produtos = []

    for elem in root.iter():
        tag = _remover_namespace(elem.tag).lower()

        if tag == "det":
            produto = {
                "codigo_fornecedor": "",
                "descricao_fornecedor": "",
                "preco_base": "",
                "quantidade_real": "",
                "gtin": "",
                "ncm": "",
                "cfop": "",
                "unidade": "",
            }

            for sub in elem.iter():
                stag = _remover_namespace(sub.tag).lower()
                texto = _safe_str(sub.text)

                if not texto:
                    continue

                # Código produto
                if stag == "cprod" and not produto["codigo_fornecedor"]:
                    produto["codigo_fornecedor"] = texto

                # Nome produto
                elif stag == "xprod" and not produto["descricao_fornecedor"]:
                    produto["descricao_fornecedor"] = texto

                # Preço unitário
                elif stag in ["vuncom", "vprod"] and not produto["preco_base"]:
                    produto["preco_base"] = _formatar_preco(texto)

                # Quantidade
                elif stag in ["qcom", "qtrib"] and not produto["quantidade_real"]:
                    produto["quantidade_real"] = texto

                # GTIN / EAN
                elif stag in ["cean", "ceantrib"] and not produto["gtin"]:
                    if texto.isdigit():
                        produto["gtin"] = texto

                # NCM
                elif stag == "ncm" and not produto["ncm"]:
                    produto["ncm"] = texto

                # CFOP
                elif stag == "cfop" and not produto["cfop"]:
                    produto["cfop"] = texto

                # Unidade
                elif stag in ["ucom", "utrib"] and not produto["unidade"]:
                    produto["unidade"] = texto

            # valida se é produto real
            if produto["descricao_fornecedor"] or produto["codigo_fornecedor"]:
                produtos.append(produto)

    if not produtos:
        return pd.DataFrame()

    df = pd.DataFrame(produtos).fillna("")

    # limpeza final
    if "quantidade_real" in df.columns:
        df["quantidade_real"] = (
            pd.to_numeric(df["quantidade_real"], errors="coerce")
            .fillna(0)
            .astype(int)
        )

    if "preco_base" in df.columns:
        df["preco_base"] = df["preco_base"].astype(str)

    return df.reset_index(drop=True)

