import io
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import pandas as pd


def _safe_text(node: Optional[ET.Element], tag: str, default: str = "") -> str:
    """
    Busca texto do primeiro filho com a tag informada ignorando namespace.
    """
    if node is None:
        return default

    for child in node.iter():
        if child.tag.split("}")[-1] == tag:
            return (child.text or "").strip()

    return default


def _find_first(node: Optional[ET.Element], tag: str) -> Optional[ET.Element]:
    """
    Retorna o primeiro elemento encontrado pela tag ignorando namespace.
    """
    if node is None:
        return None

    for child in node.iter():
        if child.tag.split("}")[-1] == tag:
            return child

    return None


def _find_all(node: Optional[ET.Element], tag: str) -> List[ET.Element]:
    """
    Retorna todos os elementos encontrados pela tag ignorando namespace.
    """
    if node is None:
        return []

    encontrados: List[ET.Element] = []
    for child in node.iter():
        if child.tag.split("}")[-1] == tag:
            encontrados.append(child)

    return encontrados


def _parse_xml_bytes(xml_bytes: bytes) -> ET.Element:
    """
    Faz parse do XML a partir de bytes.
    """
    parser = ET.XMLParser(encoding="utf-8")
    return ET.fromstring(xml_bytes, parser=parser)


def _valor_icms_aprox(det: ET.Element) -> str:
    """
    Tenta localizar um valor de ICMS dentro do item.
    """
    imposto = _find_first(det, "imposto")
    if imposto is None:
        return ""

    icms = _find_first(imposto, "ICMS")
    if icms is None:
        return ""

    for child in icms.iter():
        tag = child.tag.split("}")[-1]
        if tag == "vICMS":
            return (child.text or "").strip()

    return ""


def _aliquota_icms_aprox(det: ET.Element) -> str:
    """
    Tenta localizar uma alíquota de ICMS dentro do item.
    """
    imposto = _find_first(det, "imposto")
    if imposto is None:
        return ""

    icms = _find_first(imposto, "ICMS")
    if icms is None:
        return ""

    for child in icms.iter():
        tag = child.tag.split("}")[-1]
        if tag == "pICMS":
            return (child.text or "").strip()

    return ""


def _normalize_xml_upload_to_bytes(arquivo) -> bytes:
    """
    Streamlit UploadedFile / file-like -> bytes
    """
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


def ler_xml_nfe(arquivo) -> pd.DataFrame:
    """
    Lê XML de NF-e/NFeProc e retorna DataFrame com os produtos.
    Compatível com XML padrão da NF-e, com ou sem namespace.
    """
    xml_bytes = _normalize_xml_upload_to_bytes(arquivo)
    if not xml_bytes:
        return pd.DataFrame()

    root = _parse_xml_bytes(xml_bytes)

    # Pode vir em <nfeProc> ou <NFe>
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

    linhas: List[Dict[str, str]] = []

    for det in _find_all(inf_nfe, "det"):
        prod = _find_first(det, "prod")
        if prod is None:
            continue

        imposto = _find_first(det, "imposto")

        linha = {
            "origem_arquivo": getattr(arquivo, "name", "xml_nfe"),
            "tipo_entrada": "xml_nfe",
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
            "preco_custo": _safe_text(prod, "vUnCom"),
            "valor_total_item": _safe_text(prod, "vProd"),
            "unidade_tributavel": _safe_text(prod, "uTrib"),
            "quantidade_tributavel": _safe_text(prod, "qTrib"),
            "valor_unitario_tributavel": _safe_text(prod, "vUnTrib"),
            "frete_item": _safe_text(prod, "vFrete"),
            "seguro_item": _safe_text(prod, "vSeg"),
            "desconto_item": _safe_text(prod, "vDesc"),
            "outras_despesas_item": _safe_text(prod, "vOutro"),
            "icms_valor": _valor_icms_aprox(det),
            "icms_aliquota": _aliquota_icms_aprox(det),
            "inf_adicional_item": _safe_text(det, "infAdProd"),
            "ean": _safe_text(prod, "cEAN"),
        }

        # Mantém imposto como variável local para futuras expansões sem quebrar
        _ = imposto

        linhas.append(linha)

    return pd.DataFrame(linhas)


def arquivo_parece_xml_nfe(arquivo) -> bool:
    """
    Verifica pelo nome e por um trecho do conteúdo se parece XML de NF-e.
    """
    if arquivo is None:
        return False

    nome = getattr(arquivo, "name", "") or ""
    nome = nome.lower().strip()

    if nome.endswith(".xml"):
        try:
            xml_bytes = _normalize_xml_upload_to_bytes(arquivo)
            trecho = xml_bytes[:5000].decode("utf-8", errors="ignore").lower()
            return (
                "<nfeproc" in trecho
                or "<nfe" in trecho
                or "<infnfe" in trecho
                or "http://www.portalfiscal.inf.br/nfe" in trecho
            )
        except Exception:
            return True

    return False
