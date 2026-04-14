from __future__ import annotations

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_extractors_fields import (
    extrair_descricao,
    extrair_marca,
    extrair_nome,
    extrair_preco,
)
from bling_app_zero.core.site_crawler_extractors_images import extrair_imagens
from bling_app_zero.core.site_crawler_extractors_utils import (
    _digitos,
    _extrair_categoria,
)

from bling_app_zero.core.site_crawler_helpers import (
    buscar_produto_jsonld_crawler,
    detectar_estoque_crawler,
    extrair_json_ld_crawler,
)

try:
    from bling_app_zero.core.ia_extractor import extrair_com_ia
except Exception:
    extrair_com_ia = None

try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        pass


def extrair_produto_crawler(
    html: str,
    url: str,
    padrao_disponivel: int = 10,
    network_records=None,
    payload_origem=None,
) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    jsonlds = extrair_json_ld_crawler(soup)
    json_produto = buscar_produto_jsonld_crawler(jsonlds)

    nome = extrair_nome(soup, json_produto)
    preco = extrair_preco(soup, json_produto, html)

    if extrair_com_ia and (not nome or not preco):
        log_debug(f"[IA FALLBACK] {url}")
        produto_ia = extrair_com_ia(html, url)
        if produto_ia and produto_ia.get("Nome"):
            produto_ia["Descrição Curta"] = produto_ia.get("Descrição") or produto_ia.get("Nome")
            return produto_ia

    if not nome:
        return {}

    base = {
        "Nome": nome,
        "Preço": preco,
        "Descrição": extrair_descricao(soup, json_produto),
        "Marca": extrair_marca(json_produto),
        "Categoria": _extrair_categoria(soup),
        "GTIN/EAN": _digitos(
            json_produto.get("gtin13")
            or json_produto.get("gtin12")
            or json_produto.get("gtin14")
            or json_produto.get("gtin8")
            or json_produto.get("gtin")
        ),
        "URL Imagens Externas": extrair_imagens(soup, url, json_produto),
        "Link Externo": url,
        "Estoque": detectar_estoque_crawler(html, soup, padrao_disponivel),
    }

    base["Descrição Curta"] = base.get("Descrição") or base.get("Nome")

    log_debug(f"[EXTRACTOR FINAL] {url}")
    return base
