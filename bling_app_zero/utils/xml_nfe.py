from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import pandas as pd


def _safe_text(node: Optional[ET.Element], tag: str, default: str = "") -> str:
    try:
        if node is None:
            return default

        for child in node.iter():
            if child.tag.split("}")[-1] == tag:
                return (child.text or "").strip()

        return default
    except Exception:
        return default


def _find_first(node: Optional[ET.Element], tag: str) -> Optional[ET.Element]:
    try:
        if node is None:
            return None

        for child in node.iter():
            if child.tag.split("}")[-1] == tag:
                return child

        return None
    except Exception:
        return None


def _find_all(node: Optional[ET.Element], tag: str) -> List[ET.Element]:
    try:
        if node is None:
            return []

        encontrados: List[ET.Element] = []
        for child in node.iter():
            if child.tag.split("}")[-1] == tag:
                encontrados.append(child)

        return encontrados
    except Exception:
        return []


def _normalize_xml_upload_to_bytes(arquivo) -> bytes:
    try:
        if arquivo is None:
            return b""

        if hasattr(arquivo, "seek"):
            try:
                arquivo.seek(0)
            except Exception:
                pass

        if hasattr(arquivo, "getvalue"):
            try:
                conteudo = arquivo.getvalue()
                if isinstance(conteudo, str):
                    conteudo = conteudo.encode("utf-8")
                if isinstance(conteudo, bytes):
                    if hasattr(arquivo, "seek"):
                        try:
                            arquivo.seek(0)
                        except Exception:
                            pass
                    return conteudo
            except Exception:
                pass

        conteudo = b""
        if hasattr(arquivo, "read"):
            conteudo = arquivo.read()

        if hasattr(arquivo, "seek"):
            try:
                arquivo.seek(0)
            except Exception:
                pass

        if isinstance(conteudo, str):
            return conteudo.encode("utf-8")

        return conteudo or b""
    except Exception:
        return b""


def _to_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        txt = str(value).strip()
        if not txt:
            return default

        txt = txt.replace("R$", "").replace("\u00a0", "").replace(" ", "")

        if "," in txt and "." in txt:
            if txt.rfind(",") > txt.rfind("."):
                txt = txt.replace(".", "").replace(",", ".")
            else:
                txt = txt.replace(",", "")
        elif "," in txt:
            txt = txt.replace(".", "").replace(",", ".")
        elif txt.count(".") > 1:
            partes = txt.split(".")
            if len(partes[-1]) in {1, 2}:
                txt = "".join(partes[:-1]) + "." + partes[-1]
            else:
                txt = "".join(partes)

        return float(txt)
    except Exception:
        return default


def _find_tax_value_anywhere(node: Optional[ET.Element], possible_tags: List[str]) -> float:
    try:
        if node is None:
            return 0.0

        total = 0.0
        tags_set = {x.strip() for x in possible_tags if x and x.strip()}

        for child in node.iter():
            tag = child.tag.split("}")[-1]
            if tag in tags_set:
                total += _to_float(child.text, 0.0)

        return total
    except Exception:
        return 0.0


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

    custo_unitario = (custo_total_item / quantidade) if quantidade > 0 else 0.0

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


def _strip_accents(texto: str) -> str:
    texto = str(texto or "")
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def _texto_normalizado(texto: str) -> str:
    texto = _strip_accents(texto).upper()
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _titulo_limpo(texto: str) -> str:
    texto = str(texto or "").strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _gtin_valido(valor: str) -> str:
    texto_original = str(valor or "").strip().upper()
    if texto_original in {"", "0", "SEMGTIN", "SEM GTIN"}:
        return ""

    valor_limpo = re.sub(r"\D", "", str(valor or ""))
    if len(valor_limpo) not in {8, 12, 13, 14}:
        return ""

    return valor_limpo


def _extrair_cor(descricao: str) -> str:
    desc = _texto_normalizado(descricao)

    cores = [
        "PRETO",
        "BRANCO",
        "AZUL",
        "VERMELHO",
        "VERDE",
        "AMARELO",
        "ROSA",
        "ROXO",
        "LILAS",
        "CINZA",
        "BEGE",
        "MARROM",
        "DOURADO",
        "PRATA",
        "LARANJA",
        "VINHO",
        "NUDE",
        "OFF WHITE",
    ]

    for cor in sorted(cores, key=len, reverse=True):
        if cor in desc:
            return cor.title()

    return ""


def _extrair_tamanho(descricao: str) -> str:
    desc = _texto_normalizado(descricao)

    padroes = [
        r"\b(XXG|XGG|EXG|EXGG|GG|G|M|P|PP|XG)\b",
        r"\b(\d{2,3})\b",
        r"\b(TAM\s*\d{1,3})\b",
        r"\b(NUMERO\s*\d{1,3})\b",
    ]

    for padrao in padroes:
        encontrado = re.search(padrao, desc)
        if encontrado:
            return encontrado.group(1).strip()

    return ""


def _extrair_marca(descricao: str, fornecedor: str) -> str:
    texto_original = _titulo_limpo(descricao)
    desc = _texto_normalizado(descricao)

    padroes = [
        r"\bMARCA[:\s-]+([A-Z0-9&\.\-\/]{2,30})",
        r"\bFABRICANTE[:\s-]+([A-Z0-9&\.\-\/]{2,30})",
    ]

    for padrao in padroes:
        encontrado = re.search(padrao, desc)
        if encontrado:
            return encontrado.group(1).strip().title()

    primeiros = re.split(r"[-|/]", texto_original)
    if primeiros:
        primeiro = primeiros[0].strip()
        if 2 <= len(primeiro) <= 24 and len(primeiro.split()) <= 3:
            if primeiro.upper() not in {
                "PRODUTO",
                "ITEM",
                "UNIDADE",
                "PECAS",
                "PECA",
                "KIT",
            }:
                return primeiro

    fornecedor = _titulo_limpo(fornecedor)
    if fornecedor and len(fornecedor) <= 30:
        return fornecedor

    return ""


def _extrair_genero(descricao: str) -> str:
    desc = _texto_normalizado(descricao)

    if any(x in desc for x in ["FEMININ", "FEM ", "FEM."]):
        return "FEMININO"
    if any(x in desc for x in ["MASCULIN", "MASC ", "MASC."]):
        return "MASCULINO"
    if any(x in desc for x in ["INFANTIL", "BEBE", "KIDS", "JUVENIL"]):
        return "INFANTIL"

    return "UNISSEX"


def _extrair_material(descricao: str) -> str:
    desc = _texto_normalizado(descricao)

    materiais = {
        "ALGODAO": "Algodão",
        "POLIESTER": "Poliéster",
        "COURO": "Couro",
        "PLASTICO": "Plástico",
        "BORRACHA": "Borracha",
        "METAL": "Metal",
        "ACO": "Aço",
        "ALUMINIO": "Alumínio",
        "MADEIRA": "Madeira",
        "PVC": "PVC",
        "SILICONE": "Silicone",
        "TECIDO": "Tecido",
        "JEANS": "Jeans",
        "LYCRA": "Lycra",
    }

    for chave, valor in materiais.items():
        if chave in desc:
            return valor

    return ""


def _extrair_categoria(descricao: str) -> str:
    desc = _texto_normalizado(descricao)

    mapa = {
        "CAMISETA": "Camisetas",
        "CAMISA": "Camisas",
        "CALCA": "Calças",
        "BERMUDA": "Bermudas",
        "SHORT": "Shorts",
        "BLUSA": "Blusas",
        "VESTIDO": "Vestidos",
        "TENIS": "Tênis",
        "SAPATO": "Sapatos",
        "SANDALIA": "Sandálias",
        "CHINELO": "Chinelos",
        "BOTA": "Botas",
        "BOLSA": "Bolsas",
        "MOCHILA": "Mochilas",
        "CARTEIRA": "Carteiras",
        "BONÉ": "Bonés",
        "BONE": "Bonés",
        "OCULOS": "Óculos",
        "RELOGIO": "Relógios",
        "ANEL": "Anéis",
        "COLAR": "Colares",
        "BRINCO": "Brincos",
        "PULSEIRA": "Pulseiras",
        "KIT": "Kits",
        "CONJUNTO": "Conjuntos",
        "JAQUETA": "Jaquetas",
        "CASACO": "Casacos",
        "MEIA": "Meias",
        "CUECA": "Cuecas",
        "CALCINHA": "Calcinha",
        "SUTIA": "Sutiãs",
        "TOP": "Tops",
        "BODY": "Bodies",
        "SAIA": "Saias",
        "REGATA": "Regatas",
        "CROPPED": "Cropped",
    }

    for chave, valor in mapa.items():
        if chave in desc:
            return valor

    return "Geral"


def _extrair_modelo(descricao: str) -> str:
    texto = _titulo_limpo(descricao)

    padroes = [
        r"\bMODELO[:\s-]+([A-Za-z0-9\-\._/ ]{2,40})",
        r"\bREF[:\s-]+([A-Za-z0-9\-\._/]{2,30})",
        r"\bREFERENCIA[:\s-]+([A-Za-z0-9\-\._/]{2,30})",
    ]

    for padrao in padroes:
        encontrado = re.search(padrao, texto, flags=re.IGNORECASE)
        if encontrado:
            return encontrado.group(1).strip()

    return ""


def _gerar_codigo_fallback(numero_nfe: str, item: str, descricao: str) -> str:
    base_desc = re.sub(r"[^A-Z0-9]", "", _texto_normalizado(descricao))[:12]
    numero_nfe = re.sub(r"\D", "", str(numero_nfe or ""))
    item = re.sub(r"\D", "", str(item or ""))

    partes = [x for x in [numero_nfe, item, base_desc] if x]
    return "-".join(partes) if partes else base_desc or "ITEM-XML"


def _enriquecer_item_xml(linha: Dict[str, object]) -> Dict[str, object]:
    descricao = _titulo_limpo(linha.get("descricao") or linha.get("descricao_curta") or "")
    fornecedor = _titulo_limpo(linha.get("fornecedor") or "")
    gtin = _gtin_valido(str(linha.get("gtin") or ""))

    codigo = _titulo_limpo(str(linha.get("codigo") or ""))
    if not codigo:
        codigo = _gerar_codigo_fallback(
            str(linha.get("numero_nfe") or ""),
            str(linha.get("item") or ""),
            descricao,
        )

    marca = _extrair_marca(descricao, fornecedor)
    categoria = _extrair_categoria(descricao)
    modelo = _extrair_modelo(descricao)
    material = _extrair_material(descricao)
    genero = _extrair_genero(descricao)
    cor = _extrair_cor(descricao)
    tamanho = _extrair_tamanho(descricao)

    linha["codigo"] = codigo
    linha["nome"] = descricao
    linha["descricao_curta"] = descricao
    linha["descricao_completa"] = descricao
    linha["descricao_html"] = descricao
    linha["gtin"] = gtin
    linha["marca_inferida"] = marca
    linha["categoria_inferida"] = categoria
    linha["modelo_inferido"] = modelo
    linha["material_inferido"] = material
    linha["genero_inferido"] = genero
    linha["cor_inferida"] = cor
    linha["tamanho_inferido"] = tamanho

    linha["marca"] = marca
    linha["categoria"] = categoria
    linha["modelo"] = modelo
    linha["material"] = material
    linha["genero"] = genero

    linha["estoque"] = linha.get("quantidade", "")
    linha["custo"] = linha.get("preco_custo", "")
    linha["referencia_fornecedor"] = codigo
    linha["codigo_fabricante"] = codigo
    linha["fornecedor"] = fornecedor
    linha["origem"] = "0"
    linha["tipo"] = "P"
    linha["situacao"] = "A"
    linha["condicao"] = "NOVO"
    linha["frete_gratis"] = "NÃO"
    linha["departamento"] = "ADULTO UNISSEX"
    linha["unidade_medida"] = "CENTIMETROS"
    linha["volume"] = 1
    linha["itens_caixa"] = 1

    if cor:
        linha["variacao_nome"] = "Cor"
        linha["variacao_valor"] = cor
    elif tamanho:
        linha["variacao_nome"] = "Tamanho"
        linha["variacao_valor"] = tamanho
    else:
        linha["variacao_nome"] = ""
        linha["variacao_valor"] = ""

    linha["imagem_1"] = ""
    linha["imagem_2"] = ""
    linha["imagem_3"] = ""
    linha["imagem_4"] = ""
    linha["imagem_5"] = ""
    linha["imagem_6"] = ""
    linha["imagem_7"] = ""
    linha["imagem_8"] = ""
    linha["imagem_9"] = ""
    linha["imagem_10"] = ""
    linha["link_externo"] = ""
    linha["video"] = ""
    linha["url_video"] = ""
    linha["observacoes"] = ""

    return linha


def arquivo_parece_xml_nfe(arquivo) -> bool:
    try:
        if arquivo is None:
            return False

        nome = (getattr(arquivo, "name", "") or "").lower().strip()
        if nome and not nome.endswith(".xml"):
            return False

        xml_bytes = _normalize_xml_upload_to_bytes(arquivo)
        if not xml_bytes:
            return False

        trecho = xml_bytes[:5000].decode("utf-8", errors="ignore").lower()

        marcadores = [
            "<nfeproc",
            "<procnfe",
            "<nfe",
            "<infnfe",
            "http://www.portalfiscal.inf.br/nfe",
        ]
        return any(m in trecho for m in marcadores)
    except Exception:
        return False


def ler_xml_nfe(arquivo) -> pd.DataFrame:
    try:
        xml_bytes = _normalize_xml_upload_to_bytes(arquivo)
        if not xml_bytes:
            return pd.DataFrame()

        try:
            root = ET.fromstring(xml_bytes)
        except Exception:
            try:
                texto = xml_bytes.decode("utf-8-sig", errors="ignore")
                root = ET.fromstring(texto.encode("utf-8"))
            except Exception:
                return pd.DataFrame()

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
                "custo": round(custos["custo_unitario_float"], 6),
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

            linha = _enriquecer_item_xml(linha)
            linhas.append(linha)

        if not linhas:
            return pd.DataFrame()

        df = pd.DataFrame(linhas)
        return df.fillna("")

    except Exception:
        return pd.DataFrame()
