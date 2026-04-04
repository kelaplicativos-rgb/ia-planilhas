import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import pandas as pd


def _safe_text(node: Optional[ET.Element], tag: str, default: str = "") -> str:
    if node is None:
        return default

    for child in node.iter():
        if child.tag.split("}")[-1] == tag:
            return (child.text or "").strip()

    return default


def _find_first(node: Optional[ET.Element], tag: str) -> Optional[ET.Element]:
    if node is None:
        return None

    for child in node.iter():
        if child.tag.split("}")[-1] == tag:
            return child

    return None


def _find_all(node: Optional[ET.Element], tag: str) -> List[ET.Element]:
    if node is None:
        return []

    encontrados: List[ET.Element] = []
    for child in node.iter():
        if child.tag.split("}")[-1] == tag:
            encontrados.append(child)

    return encontrados


def _normalize_xml_upload_to_bytes(arquivo) -> bytes:
    if arquivo is None:
        return b""

    if hasattr(arquivo, "seek"):
        arquivo.seek(0)

    conteudo = arquivo.read()

    if hasattr(arquivo, "seek"):
        arquivo.seek(0)

    if isinstance(conteudo, str):
        return conteudo.encode("utf-8")

    return conteudo or b""


def _to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default

    txt = str(value).strip()
    if not txt:
        return default

    txt = txt.replace("R$", "").replace(" ", "")
    txt = txt.replace(".", "").replace(",", ".")

    try:
        return float(txt)
    except Exception:
        return default


def _find_tax_value_anywhere(node: Optional[ET.Element], possible_tags: List[str]) -> float:
    if node is None:
        return 0.0

    total = 0.0
    tags_set = {x.strip() for x in possible_tags if x.strip()}

    for child in node.iter():
        tag = child.tag.split("}")[-1]
        if tag in tags_set:
            total += _to_float(child.text, 0.0)

    return total


def _calcular_custo_item(prod: ET.Element, det: ET.Element) -> Dict[str, float]:
    quantidade = _to_float(_safe_text(prod, "qCom"), 0.0)
    valor_produto = _to_float(_safe_text(prod, "vProd"), 0.0)
    frete = _to_float(_safe_text(prod, "vFrete"), 0.0)
    seguro = _to_float(_safe_text(prod, "vSeg"), 0.0)
    outras_despesas = _to_float(_safe_text(prod, "vOutro"), 0.0)
    desconto = _to_float(_safe_text(prod, "vDesc"), 0.0)

    imposto = _find_first(det, "imposto")

    valor_ipi = _find_tax_value_anywhere(imposto, ["vIPI"])
    valor_icms_st = _find_tax_value_anywhere(imposto, ["vICMSST", "vST"])
    valor_fcp_st = _find_tax_value_anywhere(imposto, ["vFCPST"])
    valor_ii = _find_tax_value_anywhere(imposto, ["vII"])

    total_impostos = valor_ipi + valor_icms_st + valor_fcp_st + valor_ii

    custo_total_item = (
        valor_produto
        + frete
        + seguro
        + outras_despesas
        + total_impostos
        - desconto
    )

    if quantidade > 0:
        custo_unitario = custo_total_item / quantidade
    else:
        custo_unitario = 0.0

    return {
        "quantidade_float": quantidade,
        "valor_produto_float": valor_produto,
        "frete_float": frete,
        "seguro_float": seguro,
        "outras_despesas_float": outras_despesas,
        "desconto_float": desconto,
        "valor_ipi_float": valor_ipi,
        "valor_icms_st_float": valor_icms_st,
        "valor_fcp_st_float": valor_fcp_st,
        "valor_ii_float": valor_ii,
        "total_impostos_float": total_impostos,
        "custo_total_item_float": custo_total_item,
        "custo_unitario_float": custo_unitario,
    }


def arquivo_parece_xml_nfe(arquivo) -> bool:
    if arquivo is None:
        return False

    nome = (getattr(arquivo, "name", "") or "").lower().strip()
    if not nome.endswith(".xml"):
        return False

    try:
        xml_bytes = _normalize_xml_upload_to_bytes(arquivo)
        trecho = xml_bytes[:5000].decode("utf-8", errors="ignore").lower()
        return (
            "<nfeproc" in trecho
            or "<nfe" in trecho
            or "<infnfe" in trecho
            or "portalfiscal.inf.br/nfe" in trecho
        )
    except Exception:
        return True


def ler_xml_nfe(arquivo) -> pd.DataFrame:
    xml_bytes = _normalize_xml_upload_to_bytes(arquivo)
    if not xml_bytes:
        return pd.DataFrame()

    root = ET.fromstring(xml_bytes)
    inf_nfe = _find_first(root, "infNFe")
    if inf_nfe is None:
        return pd.DataFrame()

    ide = _find_first(inf_nfe, "ide")
    emit = _find_first(inf_nfe, "emit")
    dest = _find_first(inf_nfe, "dest")
    total = _find_first(inf_nfe, "ICMSTot")

    numero_nfe = _safe_text(ide, "nNF")
    serie_nfe = _safe_text(ide, "serie")
    data_emissao = _safe_text(ide, "dhEmi") or _safe_text(ide, "dEmi")
    natureza_operacao = _safe_text(ide, "natOp")

    emitente_nome = _safe_text(emit, "xNome")
    emitente_fantasia = _safe_text(emit, "xFant")
    emitente_cnpj = _safe_text(emit, "CNPJ") or _safe_text(emit, "CPF")

    destinatario_nome = _safe_text(dest, "xNome")
    destinatario_cnpj = _safe_text(dest, "CNPJ") or _safe_text(dest, "CPF")

    valor_total_nfe = _safe_text(total, "vNF")
    valor_produtos_nfe = _safe_text(total, "vProd")

    linhas: List[Dict[str, object]] = []

    for det in _find_all(inf_nfe, "det"):
        prod = _find_first(det, "prod")
        if prod is None:
            continue

        custos = _calcular_custo_item(prod, det)

        linha = {
            "origem_tipo": "xml_nfe",
            "origem_arquivo_ou_url": getattr(arquivo, "name", "xml_nfe"),
            "numero_nfe": numero_nfe,
            "serie_nfe": serie_nfe,
            "data_emissao": data_emissao,
            "natureza_operacao": natureza_operacao,
            "emitente_nome": emitente_nome,
            "emitente_fantasia": emitente_fantasia,
            "emitente_cnpj": emitente_cnpj,
            "destinatario_nome": destinatario_nome,
            "destinatario_cnpj": destinatario_cnpj,
            "valor_total_nfe": valor_total_nfe,
            "valor_produtos_nfe": valor_produtos_nfe,
            "item": det.attrib.get("nItem", ""),
            "codigo": _safe_text(prod, "cProd"),
            "descricao": _safe_text(prod, "xProd"),
            "descricao_curta": _safe_text(prod, "xProd"),
            "gtin": _safe_text(prod, "cEAN"),
            "gtin_tributavel": _safe_text(prod, "cEANTrib"),
            "ncm": _safe_text(prod, "NCM"),
            "cest": _safe_text(prod, "CEST"),
            "cfop": _safe_text(prod, "CFOP"),
            "unidade": _safe_text(prod, "uCom"),
            "quantidade": _safe_text(prod, "qCom"),
            "preco": _safe_text(prod, "vUnCom"),
            "preco_compra_xml": round(custos["custo_unitario_float"], 6),
            "preco_custo": round(custos["custo_unitario_float"], 6),
            "custo_total_item_xml": round(custos["custo_total_item_float"], 6),
            "valor_total_item": _safe_text(prod, "vProd"),
            "unidade_tributavel": _safe_text(prod, "uTrib"),
            "quantidade_tributavel": _safe_text(prod, "qTrib"),
            "valor_unitario_tributavel": _safe_text(prod, "vUnTrib"),
            "frete_item": _safe_text(prod, "vFrete"),
            "seguro_item": _safe_text(prod, "vSeg"),
            "desconto_item": _safe_text(prod, "vDesc"),
            "outras_despesas_item": _safe_text(prod, "vOutro"),
            "fornecedor": emitente_fantasia or emitente_nome,
            "cnpj_fornecedor": emitente_cnpj,
            "valor_ipi_item": round(custos["valor_ipi_float"], 6),
            "valor_icms_st_item": round(custos["valor_icms_st_float"], 6),
            "valor_fcp_st_item": round(custos["valor_fcp_st_float"], 6),
            "valor_ii_item": round(custos["valor_ii_float"], 6),
            "total_impostos_item": round(custos["total_impostos_float"], 6),
        }

        linhas.append(linha)

    return pd.DataFrame(linhas)
