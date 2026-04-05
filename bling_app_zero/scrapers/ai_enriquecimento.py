import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup


def _api_key() -> str:
    valor = (os.getenv("OPENAI_API_KEY") or "").strip()
    if valor:
        return valor

    try:
        import streamlit as st

        return str(st.secrets.get("OPENAI_API_KEY", "")).strip()
    except Exception:
        return ""


def _limpar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _somente_digitos(valor: Any) -> str:
    return re.sub(r"\D+", "", _limpar_texto(valor))


def _normalizar_gtin(valor: Any) -> str:
    digitos = _somente_digitos(valor)
    if len(digitos) in {8, 12, 13, 14}:
        return digitos
    if 8 <= len(digitos) <= 14:
        return digitos
    return ""


def _normalizar_preco(valor: Any) -> str:
    texto = _limpar_texto(valor)
    if not texto:
        return ""

    texto = texto.replace("R$", "").replace(" ", "")
    texto = texto.replace(".", "").replace(",", ".") if "," in texto else texto

    m = re.search(r"(\d+(?:\.\d{1,2})?)", texto)
    if not m:
        return ""

    try:
        numero = float(m.group(1))
        return f"{numero:.2f}"
    except Exception:
        return ""


def _compactar_html(html: str, limite: int = 28000) -> str:
    soup = BeautifulSoup(html or "", "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    texto = soup.get_text(" ", strip=True)
    texto = " ".join(texto.split())
    return texto[:limite]


def _primeiro_preenchido(*valores: Any) -> str:
    for valor in valores:
        texto = _limpar_texto(valor)
        if texto:
            return texto
    return ""


def _deduplicar_preservando_ordem(itens: Iterable[str]) -> List[str]:
    vistos = set()
    saida: List[str] = []
    for item in itens:
        valor = _limpar_texto(item)
        if not valor:
            continue
        chave = valor.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(valor)
    return saida


def _normalizar_imagens(valor: Any) -> str:
    if isinstance(valor, list):
        itens = [str(x).strip() for x in valor]
    else:
        texto = _limpar_texto(valor)
        if not texto:
            return ""
        itens = re.split(r"\s*\|\s*|\s*,\s*", texto)

    imagens = []
    for item in itens:
        item = item.strip()
        if item.startswith("http://") or item.startswith("https://"):
            imagens.append(item)

    return " | ".join(_deduplicar_preservando_ordem(imagens))


def _extrair_categoria_heuristica(soup: BeautifulSoup, html_limpo: str) -> str:
    crumbs = []

    for seletor in [
        "[aria-label='breadcrumb'] a",
        ".breadcrumb a",
        ".breadcrumbs a",
        "nav.breadcrumb a",
        "ol.breadcrumb li",
        "ul.breadcrumb li",
    ]:
        for tag in soup.select(seletor):
            txt = tag.get_text(" ", strip=True)
            if txt:
                crumbs.append(txt)

    crumbs = [
        x for x in _deduplicar_preservando_ordem(crumbs)
        if x.lower() not in {"home", "início", "inicio"}
    ]
    if crumbs:
        return " > ".join(crumbs[-3:])

    padroes = [
        r"categoria[:\s]+([A-Za-zÀ-ÿ0-9 /&\-\|]{3,120})",
        r"departamento[:\s]+([A-Za-zÀ-ÿ0-9 /&\-\|]{3,120})",
    ]
    for padrao in padroes:
        m = re.search(padrao, html_limpo, flags=re.I)
        if m:
            return _limpar_texto(m.group(1))

    return ""


def _extrair_ncm_heuristico(html_limpo: str) -> str:
    m = re.search(r"\bNCM\b[^0-9]{0,20}(\d{8})", html_limpo, flags=re.I)
    return _limpar_texto(m.group(1)) if m else ""


def _extrair_cest_heuristico(html_limpo: str) -> str:
    m = re.search(r"\bCEST\b[^0-9]{0,20}(\d{7})", html_limpo, flags=re.I)
    return _limpar_texto(m.group(1)) if m else ""


def _extrair_unidade_heuristica(html_limpo: str) -> str:
    padroes = [
        r"\bunidade\b[:\s]+([A-Za-z]{1,6})",
        r"\bembalagem\b[:\s]+([A-Za-z]{1,12})",
        r"\bmedida\b[:\s]+([A-Za-z]{1,12})",
    ]
    for padrao in padroes:
        m = re.search(padrao, html_limpo, flags=re.I)
        if m:
            return _limpar_texto(m.group(1)).upper()
    return ""


def _extrair_codigo_heuristico(html_limpo: str) -> str:
    padroes = [
        r"\bSKU\b[^A-Za-z0-9]{0,10}([A-Za-z0-9._\-\/]{3,60})",
        r"\bc[oó]d(?:igo)?\b[^A-Za-z0-9]{0,10}([A-Za-z0-9._\-\/]{3,60})",
        r"\brefer[eê]ncia\b[^A-Za-z0-9]{0,10}([A-Za-z0-9._\-\/]{3,60})",
    ]
    for padrao in padroes:
        m = re.search(padrao, html_limpo, flags=re.I)
        if m:
            return _limpar_texto(m.group(1))
    return ""


def _extrair_marca_heuristica(soup: BeautifulSoup, html_limpo: str) -> str:
    for seletor in [
        "meta[property='product:brand']",
        "meta[name='brand']",
        "meta[property='og:brand']",
    ]:
        tag = soup.select_one(seletor)
        if tag and tag.get("content"):
            return _limpar_texto(tag.get("content"))

    m = re.search(r"\bmarca\b[:\s]+([A-Za-zÀ-ÿ0-9 /&\-.]{2,80})", html_limpo, flags=re.I)
    return _limpar_texto(m.group(1)) if m else ""


def _extrair_imagens_heuristicas(soup: BeautifulSoup) -> str:
    imagens: List[str] = []

    metas = [
        "meta[property='og:image']",
        "meta[name='twitter:image']",
    ]
    for seletor in metas:
        for tag in soup.select(seletor):
            if tag.get("content"):
                imagens.append(tag.get("content"))

    for img in soup.find_all("img"):
        for attr in ("src", "data-src", "data-original", "data-zoom-image"):
            valor = img.get(attr)
            if valor and (valor.startswith("http://") or valor.startswith("https://")):
                imagens.append(valor)

    return _normalizar_imagens(imagens[:20])


def _aplicar_heuristicas(base: Dict[str, Any], html: str) -> Dict[str, Any]:
    base = dict(base or {})
    soup = BeautifulSoup(html or "", "html.parser")
    html_limpo = _compactar_html(html, limite=22000)

    base["codigo"] = _primeiro_preenchido(base.get("codigo"), _extrair_codigo_heuristico(html_limpo))
    base["gtin"] = _normalizar_gtin(_primeiro_preenchido(base.get("gtin")))
    base["preco"] = _normalizar_preco(_primeiro_preenchido(base.get("preco")))
    base["preco_custo"] = _normalizar_preco(_primeiro_preenchido(base.get("preco_custo"), base.get("preco")))
    base["marca"] = _primeiro_preenchido(base.get("marca"), _extrair_marca_heuristica(soup, html_limpo))
    base["categoria"] = _primeiro_preenchido(base.get("categoria"), _extrair_categoria_heuristica(soup, html_limpo))
    base["ncm"] = _primeiro_preenchido(base.get("ncm"), _extrair_ncm_heuristico(html_limpo))
    base["cest"] = _primeiro_preenchido(base.get("cest"), _extrair_cest_heuristico(html_limpo))
    base["unidade"] = _primeiro_preenchido(base.get("unidade"), _extrair_unidade_heuristica(html_limpo))
    base["imagens"] = _normalizar_imagens(_primeiro_preenchido(base.get("imagens"), _extrair_imagens_heuristicas(soup)))
    base["nome"] = _limpar_texto(base.get("nome"))
    base["descricao_curta"] = _primeiro_preenchido(base.get("descricao_curta"), base.get("nome"))
    base["descricao"] = _primeiro_preenchido(base.get("descricao"), base.get("nome"))

    return base


def _extrair_json_objeto(texto: str) -> Optional[Dict[str, Any]]:
    texto = _limpar_texto(texto)
    if not texto:
        return None

    candidatos = [texto]

    bloco = re.search(r"\{.*\}", texto, flags=re.S)
    if bloco:
        candidatos.append(bloco.group(0))

    for candidato in candidatos:
        try:
            dado = json.loads(candidato)
            if isinstance(dado, dict):
                return dado
        except Exception:
            continue

    return None


def _prompt_sistema() -> str:
    return (
        "Você é um extrator especialista em e-commerce BR e padronização para Bling. "
        "Receberá URL, JSON preliminar e HTML resumido de uma página de produto. "
        "Sua tarefa é corrigir e completar APENAS quando houver evidência no HTML. "
        "Você deve lidar com HTML bagunçado, nomes incompletos, breadcrumbs, tabelas técnicas, "
        "metadados, sku, gtin/ean, marca, NCM, CEST, unidade e imagens. "
        "Nunca invente informação. "
        "Retorne SOMENTE JSON válido com estas chaves: "
        "nome, descricao, descricao_curta, codigo, gtin, preco, preco_custo, marca, categoria, "
        "ncm, cest, unidade, imagens, disponibilidade_site, fornecedor, cnpj_fornecedor. "
        "Regras: "
        "1) gtin só números com 8 a 14 dígitos; "
        "2) preco e preco_custo em formato decimal com ponto, ex.: 149.90; "
        "3) imagens em string única separada por ' | '; "
        "4) categoria em formato amigável para cadastro; "
        "5) se não houver evidência, deixe vazio."
    )


def _chamar_openai(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    api_key = _api_key()
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        resposta = client.chat.completions.create(
            model="gpt-4.1-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _prompt_sistema()},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
        )

        texto = (
            resposta.choices[0].message.content
            if resposta and getattr(resposta, "choices", None)
            else ""
        )

        return _extrair_json_objeto(texto or "")
    except Exception:
        return None


def _mesclar_campos(base: Dict[str, Any], corrigido: Dict[str, Any]) -> Dict[str, Any]:
    saida = dict(base or {})

    for chave in [
        "nome",
        "descricao",
        "descricao_curta",
        "codigo",
        "gtin",
        "preco",
        "preco_custo",
        "marca",
        "categoria",
        "ncm",
        "cest",
        "unidade",
        "imagens",
        "disponibilidade_site",
        "fornecedor",
        "cnpj_fornecedor",
    ]:
        valor = corrigido.get(chave, "")
        if chave == "gtin":
            valor = _normalizar_gtin(valor)
        elif chave in {"preco", "preco_custo"}:
            valor = _normalizar_preco(valor)
        elif chave == "imagens":
            valor = _normalizar_imagens(valor)
        else:
            valor = _limpar_texto(valor)

        if valor:
            saida[chave] = valor

    saida["descricao_curta"] = _primeiro_preenchido(saida.get("descricao_curta"), saida.get("nome"))
    saida["descricao"] = _primeiro_preenchido(saida.get("descricao"), saida.get("nome"))

    if _limpar_texto(saida.get("preco")) and not _limpar_texto(saida.get("preco_custo")):
        saida["preco_custo"] = _normalizar_preco(saida.get("preco"))

    return saida


def enriquecer_produto_com_ia(dados: Dict, html: str, url: str) -> Dict:
    base = _aplicar_heuristicas(dict(dados or {}), html)

    payload = {
        "url": _limpar_texto(url),
        "dados_extraidos": base,
        "html_resumido": _compactar_html(html),
    }

    corrigido = _chamar_openai(payload)

    if not corrigido:
        base["ia_enriquecida"] = "nao"
        return base

    final = _mesclar_campos(base, corrigido)
    final["ia_enriquecida"] = "sim"
    return final
