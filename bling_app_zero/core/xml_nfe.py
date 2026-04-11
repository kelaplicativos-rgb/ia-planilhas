from __future__ import annotations

import xml.etree.ElementTree as ET

import pandas as pd


def _xml_tag_local(tag: str) -> str:
    try:
        return str(tag).split("}", 1)[-1].strip().lower()
    except Exception:
        return str(tag or "").strip().lower()


def _xml_child(parent: ET.Element | None, *nomes: str) -> ET.Element | None:
    if parent is None:
        return None

    nomes_normalizados = {_xml_tag_local(nome) for nome in nomes if nome}

    for child in list(parent):
        if _xml_tag_local(child.tag) in nomes_normalizados:
            return child

    return None


def _xml_children(parent: ET.Element | None, *nomes: str) -> list[ET.Element]:
    if parent is None:
        return []

    nomes_normalizados = {_xml_tag_local(nome) for nome in nomes if nome}
    saida: list[ET.Element] = []

    for child in parent.iter():
        if child is parent:
            continue
        if _xml_tag_local(child.tag) in nomes_normalizados:
            saida.append(child)

    return saida


def _xml_text(parent: ET.Element | None, *caminho: str) -> str:
    atual = parent
    for nome in caminho:
        atual = _xml_child(atual, nome)
        if atual is None:
            return ""

    try:
        return str((atual.text or "")).strip()
    except Exception:
        return ""


def _xml_text_multi(parent: ET.Element | None, caminhos: list[tuple[str, ...]]) -> str:
    for caminho in caminhos:
        valor = _xml_text(parent, *caminho)
        if valor:
            return valor
    return ""


def _normalizar_numero_texto(valor) -> float | int | str:
    try:
        texto = str(valor or "").strip()
        if not texto:
            return ""

        texto = (
            texto.replace(".", "").replace(",", ".")
            if texto.count(",") == 1 and texto.count(".") >= 1
            else texto.replace(",", ".")
        )
        numero = float(texto)
        if numero.is_integer():
            return int(numero)
        return numero
    except Exception:
        return str(valor or "").strip()


def _normalizar_gtin_xml(valor: str) -> str:
    texto = str(valor or "").strip()
    if texto.lower() in {"sem gtin", "sem ean", "no gtin", "nan", "none"}:
        return ""
    return texto


def _obter_icms_xml(imposto: ET.Element | None) -> tuple[str, str]:
    if imposto is None:
        return "", ""

    icms = _xml_child(imposto, "ICMS")
    if icms is None:
        return "", ""

    grupo = None
    for child in list(icms):
        grupo = child
        break

    if grupo is None:
        return "", ""

    origem = _xml_text(grupo, "orig")
    cst = _xml_text_multi(
        grupo,
        [
            ("CSOSN",),
            ("CST",),
        ],
    )
    return origem, cst


def ler_conteudo_xml_upload(arquivo_xml) -> str:
    try:
        arquivo_xml.seek(0)
        conteudo = arquivo_xml.read()

        if isinstance(conteudo, bytes):
            for encoding in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    return conteudo.decode(encoding)
                except Exception:
                    continue
            return conteudo.decode("utf-8", errors="ignore")

        return str(conteudo or "")
    except Exception:
        return ""


def extrair_dataframe_nfe(conteudo_xml: str) -> pd.DataFrame:
    conteudo_xml = str(conteudo_xml or "").strip()
    if not conteudo_xml:
        return pd.DataFrame()

    root = ET.fromstring(conteudo_xml)

    inf_nfe = None
    for node in root.iter():
        if _xml_tag_local(node.tag) == "infnfe":
            inf_nfe = node
            break

    if inf_nfe is None:
        raise ValueError("XML sem bloco infNFe.")

    ide = _xml_child(inf_nfe, "ide")
    emit = _xml_child(inf_nfe, "emit")
    dest = _xml_child(inf_nfe, "dest")
    total = _xml_child(inf_nfe, "total")
    icms_tot = _xml_child(total, "ICMSTot") if total is not None else None

    numero_nf = _xml_text(ide, "nNF")
    serie_nf = _xml_text(ide, "serie")
    data_emissao = _xml_text_multi(ide, [("dhEmi",), ("dEmi",)])
    chave_nfe = str(inf_nfe.attrib.get("Id", "") or "").replace("NFe", "", 1)

    emitente = _xml_text(emit, "xNome")
    cnpj_emitente = _xml_text_multi(emit, [("CNPJ",), ("CPF",)])
    destinatario = _xml_text(dest, "xNome")
    cnpj_destinatario = _xml_text_multi(dest, [("CNPJ",), ("CPF",)])

    valor_nf = _normalizar_numero_texto(_xml_text(icms_tot, "vNF"))
    valor_produtos_nf = _normalizar_numero_texto(_xml_text(icms_tot, "vProd"))
    valor_frete_nf = _normalizar_numero_texto(_xml_text(icms_tot, "vFrete"))
    valor_seguro_nf = _normalizar_numero_texto(_xml_text(icms_tot, "vSeg"))
    valor_desconto_nf = _normalizar_numero_texto(_xml_text(icms_tot, "vDesc"))
    valor_outros_nf = _normalizar_numero_texto(_xml_text(icms_tot, "vOutro"))

    linhas: list[dict] = []

    for det in _xml_children(inf_nfe, "det"):
        prod = _xml_child(det, "prod")
        if prod is None:
            continue

        imposto = _xml_child(det, "imposto")
        origem_icms, cst_icms = _obter_icms_xml(imposto)

        quantidade = _normalizar_numero_texto(_xml_text(prod, "qCom"))
        quantidade_trib = _normalizar_numero_texto(_xml_text(prod, "qTrib"))
        valor_unitario = _normalizar_numero_texto(_xml_text(prod, "vUnCom"))
        valor_unitario_trib = _normalizar_numero_texto(_xml_text(prod, "vUnTrib"))
        valor_total = _normalizar_numero_texto(_xml_text(prod, "vProd"))

        linhas.append(
            {
                "Número NF": numero_nf,
                "Série NF": serie_nf,
                "Chave NF-e": chave_nfe,
                "Data Emissão": data_emissao,
                "Emitente": emitente,
                "CNPJ Emitente": cnpj_emitente,
                "Destinatário": destinatario,
                "CNPJ Destinatário": cnpj_destinatario,
                "Código": _xml_text(prod, "cProd"),
                "Descrição": _xml_text(prod, "xProd"),
                "Descrição Curta": _xml_text(prod, "xProd"),
                "Unidade": _xml_text(prod, "uCom"),
                "Unidade Tributável": _xml_text_multi(prod, [("uTrib",), ("uCom",)]),
                "Quantidade": quantidade,
                "Quantidade Tributável": quantidade_trib or quantidade,
                "Preço de custo": valor_unitario,
                "Preço unitário": valor_unitario,
                "Preço unitário tributável": valor_unitario_trib or valor_unitario,
                "Preço total": valor_total,
                "Valor total": valor_total,
                "NCM": _xml_text(prod, "NCM"),
                "CEST": _xml_text(prod, "CEST"),
                "CFOP": _xml_text(prod, "CFOP"),
                "GTIN": _normalizar_gtin_xml(_xml_text_multi(prod, [("cEAN",), ("cBarra",)])),
                "GTIN Tributário": _normalizar_gtin_xml(
                    _xml_text_multi(prod, [("cEANTrib",), ("cBarraTrib",), ("cEAN",)])
                ),
                "Origem ICMS": origem_icms,
                "CST/CSOSN": cst_icms,
                "Marca": "",
                "Categoria": "",
                "Valor NF": valor_nf,
                "Valor Produtos NF": valor_produtos_nf,
                "Valor Frete NF": valor_frete_nf,
                "Valor Seguro NF": valor_seguro_nf,
                "Valor Desconto NF": valor_desconto_nf,
                "Valor Outros NF": valor_outros_nf,
            }
        )

    df_xml = pd.DataFrame(linhas)
    if df_xml.empty:
        raise ValueError("XML sem itens <det> para converter.")

    return df_xml


def converter_upload_xml_para_dataframe(arquivo_xml) -> pd.DataFrame:
    conteudo = ler_conteudo_xml_upload(arquivo_xml)
    if not str(conteudo or "").strip():
        return pd.DataFrame()
    return extrair_dataframe_nfe(conteudo)
