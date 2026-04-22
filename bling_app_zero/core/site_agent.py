
"""
SITE AGENT (ORQUESTRADOR GLOBAL)

Responsável por:
- detectar fornecedor
- executar fornecedor específico
- usar fallback genérico
- preservar auth_context até a coleta real
- padronizar o resultado

BLINGFIX:
- reduz dependência de fornecedores que usam Playwright
- adiciona fallback interno real com requests + bs4 + heurística
- só depende do registry se ele funcionar
- mantém diagnóstico mesmo quando cai no fallback
"""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

from bling_app_zero.core.suppliers.registry import SupplierRegistry, get_registry


class SiteAgent:
    def __init__(self) -> None:
        self.registry: SupplierRegistry = get_registry()

    # ------------------------------------------------------------------
    # EXECUÇÃO
    # ------------------------------------------------------------------
    def executar(
        self,
        url: str,
        *,
        auth_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        url = self._normalizar_url(url)
        if not url:
            return []

        fornecedor = self._detectar_fornecedor(url)
        produtos: List[Dict[str, Any]] = []
        kwargs_limpos = self._filtrar_kwargs_fornecedor(kwargs)

        if auth_context:
            kwargs_limpos["auth_context"] = auth_context

        # 1) fornecedor específico
        if fornecedor is not None:
            try:
                self._log(f"[SITE_AGENT] fornecedor detectado: {getattr(fornecedor, 'nome', fornecedor.__class__.__name__)}")
                produtos = fornecedor.fetch(url, **kwargs_limpos)
                produtos = self._validar_com_fornecedor(fornecedor, produtos)
                if produtos:
                    self._log(f"[SITE_AGENT] fornecedor específico retornou {len(produtos)} produto(s)")
            except Exception as exc:
                self._log(f"[ERRO fornecedor específico] {exc}")

        # 2) fallback registry genérico
        if not produtos:
            fornecedor_generico = self._obter_fornecedor_generico()
            if fornecedor_generico is not None and fornecedor_generico is not fornecedor:
                self._log("[FALLBACK] usando GenericSupplier do registry")
                try:
                    produtos = fornecedor_generico.fetch(url, **kwargs_limpos)
                    produtos = self._validar_com_fornecedor(fornecedor_generico, produtos)
                    if produtos:
                        self._log(f"[SITE_AGENT] GenericSupplier retornou {len(produtos)} produto(s)")
                except Exception as exc:
                    self._log(f"[ERRO fallback GenericSupplier] {exc}")

        # 3) fallback interno requests + bs4
        if not produtos:
            self._log("[FALLBACK INTERNO] usando requests + bs4 + heurística")
            try:
                produtos = self._buscar_com_fallback_interno(
                    url=url,
                    auth_context=auth_context,
                    limite=int(kwargs.get("limite", kwargs.get("limite_links", 120)) or 120),
                )
                if produtos:
                    self._log(f"[SITE_AGENT] fallback interno retornou {len(produtos)} produto(s)")
            except Exception as exc:
                self._log(f"[ERRO fallback interno] {exc}")

        return self._padronizar(produtos)

    # ------------------------------------------------------------------
    # COMPATIBILIDADE
    # ------------------------------------------------------------------
    def buscar_produtos(self, base_url: str, **kwargs) -> pd.DataFrame:
        return self.buscar_dataframe(base_url=base_url, **kwargs)

    def buscar_dataframe(
        self,
        *,
        base_url: str,
        diagnostico: bool = False,
        auth_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> pd.DataFrame:
        url = self._normalizar_url(base_url)
        fornecedor = self._detectar_fornecedor(url)

        produtos = self.executar(
            url,
            auth_context=auth_context,
            **kwargs,
        )
        df = self.para_dataframe(produtos)

        if diagnostico:
            diag = self._diagnostico_basico(
                url=url,
                fornecedor=fornecedor,
                produtos=produtos,
                auth_context=auth_context,
            )
            self._aplicar_diagnostico_streamlit(diag)

        return df

    # ------------------------------------------------------------------
    # REGISTRY
    # ------------------------------------------------------------------
    def _detectar_fornecedor(self, url: str):
        try:
            return self.registry.detectar(url)
        except Exception:
            return None

    def _obter_fornecedor_generico(self):
        for supplier in getattr(self.registry, "suppliers", []):
            try:
                nome = str(getattr(supplier, "nome", "") or "").strip().lower()
                classe = supplier.__class__.__name__.strip().lower()
                if "genérico" in nome or "generico" in nome or "generic" in classe:
                    return supplier
            except Exception:
                continue
        return None

    def _validar_com_fornecedor(self, fornecedor: Any, produtos: Any) -> List[Dict[str, Any]]:
        if not isinstance(produtos, list):
            return []

        try:
            if hasattr(fornecedor, "validar_produtos"):
                produtos = fornecedor.validar_produtos(produtos)
        except Exception:
            pass

        return produtos if isinstance(produtos, list) else []

    # ------------------------------------------------------------------
    # FALLBACK INTERNO
    # ------------------------------------------------------------------
    def _build_session(self, auth_context: Optional[Dict[str, Any]] = None) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
        )

        if isinstance(auth_context, dict):
            headers = auth_context.get("headers", {}) or {}
            if isinstance(headers, dict):
                for k, v in headers.items():
                    k_txt = self._texto_limpo(k)
                    v_txt = self._texto_limpo(v)
                    if k_txt and v_txt:
                        session.headers[k_txt] = v_txt

            cookies = auth_context.get("cookies", []) or []
            if isinstance(cookies, list):
                for cookie in cookies:
                    if not isinstance(cookie, dict):
                        continue
                    nome = self._texto_limpo(cookie.get("name"))
                    valor = self._texto_limpo(cookie.get("value"))
                    dominio = self._texto_limpo(cookie.get("domain"))
                    caminho = self._texto_limpo(cookie.get("path")) or "/"
                    if nome and valor:
                        try:
                            session.cookies.set(nome, valor, domain=dominio or None, path=caminho)
                        except Exception:
                            try:
                                session.cookies.set(nome, valor)
                            except Exception:
                                pass

        return session

    def _buscar_com_fallback_interno(
        self,
        *,
        url: str,
        auth_context: Optional[Dict[str, Any]] = None,
        limite: int = 120,
    ) -> List[Dict[str, Any]]:
        session = self._build_session(auth_context=auth_context)

        paginas_alvo: List[str] = []
        vistos_paginas: Set[str] = set()

        products_url = self._texto_limpo((auth_context or {}).get("products_url"))
        if products_url:
            products_url = self._normalizar_url(products_url)
            if products_url:
                paginas_alvo.append(products_url)

        url = self._normalizar_url(url)
        if url and url not in paginas_alvo:
            paginas_alvo.append(url)

        links_produtos: List[str] = []
        produtos_coletados: List[Dict[str, Any]] = []

        for pagina in paginas_alvo:
            if pagina in vistos_paginas:
                continue
            vistos_paginas.add(pagina)

            html, final_url = self._get_html(session, pagina)
            if not html:
                continue

            # 1) tenta JSON-LD da página atual
            jsonld_produtos = self._extrair_produtos_jsonld(html, final_url)
            if jsonld_produtos:
                produtos_coletados.extend(jsonld_produtos)

            # 2) se a página atual já parece ser produto, extrai direto
            if self._pagina_parece_produto(html, final_url):
                produto = self._extrair_produto_da_pagina(html, final_url)
                if produto:
                    produtos_coletados.append(produto)

            # 3) coleta links de produto da página/categoria
            novos_links = self._extrair_links_produto(html, final_url, limite=limite)
            for link in novos_links:
                if link not in links_produtos:
                    links_produtos.append(link)

            # 4) tenta paginação simples
            links_paginacao = self._extrair_links_paginacao(html, final_url, limite_paginas=8)
            for link_pag in links_paginacao:
                if link_pag in vistos_paginas:
                    continue
                vistos_paginas.add(link_pag)

                html_pag, final_pag = self._get_html(session, link_pag)
                if not html_pag:
                    continue

                jsonld_pag = self._extrair_produtos_jsonld(html_pag, final_pag)
                if jsonld_pag:
                    produtos_coletados.extend(jsonld_pag)

                for link in self._extrair_links_produto(html_pag, final_pag, limite=limite):
                    if link not in links_produtos:
                        links_produtos.append(link)

                if len(links_produtos) >= limite:
                    break

            if len(links_produtos) >= limite:
                break

        # 5) visita links de produto
        for link_produto in links_produtos[:limite]:
            html_prod, final_prod = self._get_html(session, link_produto)
            if not html_prod:
                continue

            produto = self._extrair_produto_da_pagina(html_prod, final_prod)
            if produto:
                produtos_coletados.append(produto)

        produtos_coletados = self._padronizar(produtos_coletados)
        return produtos_coletados

    def _get_html(self, session: requests.Session, url: str) -> Tuple[str, str]:
        try:
            resp = session.get(url, timeout=30, allow_redirects=True)
            if not resp.ok:
                return "", self._normalizar_url(url)
            return resp.text or "", str(resp.url)
        except Exception as exc:
            self._log(f"[GET_HTML ERRO] {url} -> {exc}")
            return "", self._normalizar_url(url)

    def _extrair_produtos_jsonld(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html or "", "html.parser")
        produtos: List[Dict[str, Any]] = []

        for tag in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
            texto = tag.string or tag.get_text(" ", strip=True) or ""
            texto = texto.strip()
            if not texto:
                continue

            try:
                data = json.loads(texto)
            except Exception:
                continue

            for item in self._iterar_jsonld_items(data):
                produto = self._jsonld_item_para_produto(item, base_url=base_url)
                if produto:
                    produtos.append(produto)

        return produtos

    def _iterar_jsonld_items(self, data: Any) -> List[Dict[str, Any]]:
        itens: List[Dict[str, Any]] = []

        def _walk(obj: Any) -> None:
            if isinstance(obj, dict):
                if obj.get("@type") == "Product":
                    itens.append(obj)
                for valor in obj.values():
                    _walk(valor)
            elif isinstance(obj, list):
                for valor in obj:
                    _walk(valor)

        _walk(data)
        return itens

    def _jsonld_item_para_produto(self, item: Dict[str, Any], base_url: str) -> Optional[Dict[str, Any]]:
        if not isinstance(item, dict):
            return None

        offers = item.get("offers")
        preco = ""
        estoque = ""
        disponibilidade = ""

        if isinstance(offers, list) and offers:
            offers = offers[0]

        if isinstance(offers, dict):
            preco = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice") or ""
            disponibilidade = self._texto_limpo(offers.get("availability"))
            estoque = 0 if "outofstock" in disponibilidade.lower() else 1

        imagens = item.get("image", [])
        if isinstance(imagens, str):
            imagens = [imagens]
        elif not isinstance(imagens, list):
            imagens = []

        marca = ""
        brand = item.get("brand")
        if isinstance(brand, dict):
            marca = brand.get("name") or ""
        elif isinstance(brand, str):
            marca = brand

        sku = item.get("sku") or item.get("mpn") or ""
        gtin = (
            item.get("gtin13")
            or item.get("gtin12")
            or item.get("gtin14")
            or item.get("gtin8")
            or item.get("gtin")
            or ""
        )

        url_produto = self._normalizar_url(item.get("url") or base_url)

        nome = self._texto_limpo(item.get("name"))
        if not nome and not url_produto:
            return None

        return {
            "url_produto": url_produto,
            "nome": nome,
            "sku": sku,
            "marca": marca,
            "categoria": self._texto_limpo(item.get("category")),
            "estoque": estoque,
            "preco": preco,
            "gtin": gtin,
            "descricao": self._texto_limpo(item.get("description")),
            "imagens": imagens,
        }

    def _pagina_parece_produto(self, html: str, url: str) -> bool:
        page = (html or "").lower()
        url_l = (url or "").lower()

        sinais = 0

        if any(token in url_l for token in ["/produto", "/produtos/", "/product", "/p/"]):
            sinais += 1
        if '"@type":"product"' in page or '"@type": "product"' in page:
            sinais += 2
        if any(token in page for token in ["sku", "ean", "gtin", "código", "codigo do produto"]):
            sinais += 1
        if any(token in page for token in ["comprar", "adicionar ao carrinho", "buy now", "add to cart"]):
            sinais += 1
        if re.search(r"r\$\s*\d", page):
            sinais += 1

        return sinais >= 2

    def _extrair_links_produto(self, html: str, base_url: str, limite: int = 120) -> List[str]:
        soup = BeautifulSoup(html or "", "html.parser")
        base_host = self._hostname(base_url)
        links: List[str] = []
        vistos: Set[str] = set()

        for a in soup.find_all("a", href=True):
            href = self._texto_limpo(a.get("href"))
            if not href:
                continue

            url = urljoin(base_url, href)
            url = self._limpar_url(url)

            if not url:
                continue
            if self._hostname(url) != base_host:
                continue
            if not self._url_parece_produto(url):
                continue
            if url in vistos:
                continue

            vistos.add(url)
            links.append(url)

            if len(links) >= limite:
                break

        return links

    def _extrair_links_paginacao(self, html: str, base_url: str, limite_paginas: int = 8) -> List[str]:
        soup = BeautifulSoup(html or "", "html.parser")
        base_host = self._hostname(base_url)
        links: List[str] = []
        vistos: Set[str] = set()

        for a in soup.find_all("a", href=True):
            href = self._texto_limpo(a.get("href"))
            texto = self._texto_limpo(a.get_text(" ", strip=True)).lower()
            if not href:
                continue

            url = urljoin(base_url, href)
            url = self._limpar_url(url)
            if not url:
                continue
            if self._hostname(url) != base_host:
                continue

            url_l = url.lower()
            parece_paginacao = (
                any(token in url_l for token in ["page=", "/page/", "pagina=", "p=", "?pg="])
                or texto in {"próxima", "proxima", "next", ">", ">>"}
                or "próxima" in texto
                or "proxima" in texto
            )

            if not parece_paginacao:
                continue
            if url in vistos:
                continue

            vistos.add(url)
            links.append(url)
            if len(links) >= limite_paginas:
                break

        return links

    def _extrair_produto_da_pagina(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        jsonld = self._extrair_produtos_jsonld(html, url)
        if jsonld:
            melhor = jsonld[0]
            if self._texto_limpo(melhor.get("nome")) or self._texto_limpo(melhor.get("url_produto")):
                return melhor

        soup = BeautifulSoup(html or "", "html.parser")
        texto_pagina = soup.get_text(" ", strip=True)

        nome = self._extrair_nome_produto(soup)
        preco = self._extrair_preco(texto_pagina, soup)
        sku = self._extrair_sku(texto_pagina, soup)
        gtin = self._extrair_gtin(texto_pagina, soup)
        marca = self._extrair_marca(soup, texto_pagina, nome)
        categoria = self._extrair_categoria(soup)
        descricao = self._extrair_descricao(soup)
        imagens = self._extrair_imagens(soup, url)
        estoque = self._extrair_estoque(texto_pagina, soup)

        if not nome and not sku and not gtin:
            return None

        return {
            "url_produto": url,
            "nome": nome,
            "sku": sku,
            "marca": marca,
            "categoria": categoria,
            "estoque": estoque,
            "preco": preco,
            "gtin": gtin,
            "descricao": descricao,
            "imagens": imagens,
        }

    def _extrair_nome_produto(self, soup: BeautifulSoup) -> str:
        candidatos = [
            {"name": "meta", "attrs": {"property": "og:title"}},
            {"name": "meta", "attrs": {"name": "twitter:title"}},
            {"name": "h1", "attrs": {}},
            {"name": True, "attrs": {"itemprop": "name"}},
            {"name": True, "attrs": {"class": re.compile(r"(product.*title|produto.*titulo|title)", re.I)}},
        ]

        for cfg in candidatos:
            try:
                tag = soup.find(cfg["name"], attrs=cfg["attrs"])
                if not tag:
                    continue
                if tag.name == "meta":
                    valor = self._texto_limpo(tag.get("content"))
                else:
                    valor = self._texto_limpo(tag.get_text(" ", strip=True))
                valor = unescape(valor)
                if valor and len(valor) >= 3:
                    return valor
            except Exception:
                continue
        return ""

    def _extrair_preco(self, texto_pagina: str, soup: BeautifulSoup) -> Any:
        for tag in soup.find_all(attrs={"content": True}):
            try:
                content = self._texto_limpo(tag.get("content"))
                if re.fullmatch(r"\d+[.,]\d{2}", content):
                    return content
            except Exception:
                pass

        match = re.search(r"r\$\s*([\d\.\,]+)", texto_pagina.lower())
        if match:
            return match.group(1)
        return ""

    def _extrair_sku(self, texto_pagina: str, soup: BeautifulSoup) -> str:
        for tag in soup.find_all(attrs={"itemprop": re.compile(r"sku", re.I)}):
            valor = self._texto_limpo(tag.get("content") or tag.get_text(" ", strip=True))
            if valor:
                return valor

        padroes = [
            r"(?:sku|código|codigo)\s*[:#]?\s*([a-zA-Z0-9\-_./]+)",
            r"(?:ref\.?|referência|referencia)\s*[:#]?\s*([a-zA-Z0-9\-_./]+)",
        ]
        for padrao in padroes:
            match = re.search(padrao, texto_pagina, flags=re.I)
            if match:
                return self._texto_limpo(match.group(1))

        return ""

    def _extrair_gtin(self, texto_pagina: str, soup: BeautifulSoup) -> str:
        for chave in ["gtin13", "gtin12", "gtin14", "gtin8", "gtin"]:
            try:
                tag = soup.find(attrs={"itemprop": re.compile(chave, re.I)})
                if tag:
                    valor = self._texto_limpo(tag.get("content") or tag.get_text(" ", strip=True))
                    numeros = re.sub(r"\D", "", valor)
                    if numeros:
                        return numeros
            except Exception:
                continue

        match = re.search(r"(?:ean|gtin)\s*[:#]?\s*(\d{8,14})", texto_pagina, flags=re.I)
        if match:
            return match.group(1)

        return ""

    def _extrair_marca(self, soup: BeautifulSoup, texto_pagina: str, nome: str) -> str:
        for tag in soup.find_all(attrs={"itemprop": re.compile(r"brand", re.I)}):
            valor = self._texto_limpo(tag.get("content") or tag.get_text(" ", strip=True))
            if valor:
                return valor

        padroes = [
            r"(?:marca)\s*[:#]?\s*([A-Za-z0-9À-ÿ\-_ ]{2,60})",
        ]
        for padrao in padroes:
            match = re.search(padrao, texto_pagina, flags=re.I)
            if match:
                return self._texto_limpo(match.group(1))

        # fallback leve: primeira palavra em caixa alta no começo do nome
        nome_limpo = self._texto_limpo(nome)
        if nome_limpo:
            primeira = nome_limpo.split(" ")[0].strip()
            if primeira and len(primeira) > 1:
                return primeira

        return ""

    def _extrair_categoria(self, soup: BeautifulSoup) -> str:
        breadcrumbs = []
        try:
            for tag in soup.find_all(attrs={"class": re.compile(r"breadcrumb", re.I)}):
                texto = self._texto_limpo(tag.get_text(" > ", strip=True))
                if texto:
                    breadcrumbs.append(texto)
            if breadcrumbs:
                return breadcrumbs[0]
        except Exception:
            pass
        return ""

    def _extrair_descricao(self, soup: BeautifulSoup) -> str:
        candidatos = [
            {"name": True, "attrs": {"itemprop": re.compile(r"description", re.I)}},
            {"name": True, "attrs": {"class": re.compile(r"(description|descricao)", re.I)}},
            {"name": "meta", "attrs": {"name": "description"}},
            {"name": "meta", "attrs": {"property": "og:description"}},
        ]

        for cfg in candidatos:
            try:
                tag = soup.find(cfg["name"], attrs=cfg["attrs"])
                if not tag:
                    continue
                if tag.name == "meta":
                    valor = self._texto_limpo(tag.get("content"))
                else:
                    valor = self._texto_limpo(tag.get_text(" ", strip=True))
                if valor and len(valor) >= 10:
                    return valor[:5000]
            except Exception:
                continue

        return ""

    def _extrair_imagens(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        imagens: List[str] = []
        vistos: Set[str] = set()

        metas = [
            soup.find("meta", attrs={"property": "og:image"}),
            soup.find("meta", attrs={"name": "twitter:image"}),
        ]
        for meta in metas:
            if meta:
                url = self._limpar_url(urljoin(base_url, self._texto_limpo(meta.get("content"))))
                if url and url not in vistos:
                    vistos.add(url)
                    imagens.append(url)

        for img in soup.find_all("img"):
            src = self._texto_limpo(
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
                or img.get("data-lazy")
            )
            if not src:
                continue
            url = self._limpar_url(urljoin(base_url, src))
            if not url:
                continue
            if any(token in url.lower() for token in ["logo", "icon", "sprite", "banner"]):
                continue
            if url in vistos:
                continue
            vistos.add(url)
            imagens.append(url)
            if len(imagens) >= 12:
                break

        return imagens

    def _extrair_estoque(self, texto_pagina: str, soup: BeautifulSoup) -> Any:
        texto = self._texto_limpo(texto_pagina).lower()

        if any(termo in texto for termo in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado", "out of stock"]):
            return 0

        padroes_qtd = [
            r"(\d+)\s*(?:unidades|unidade|itens|item)\s*(?:em estoque|disponíveis|disponiveis)",
            r"estoque\s*[:#]?\s*(\d+)",
        ]
        for padrao in padroes_qtd:
            match = re.search(padrao, texto, flags=re.I)
            if match:
                try:
                    return int(match.group(1))
                except Exception:
                    pass

        if any(termo in texto for termo in ["em estoque", "disponível", "disponivel", "available", "in stock"]):
            return 1

        for tag in soup.find_all(attrs={"class": re.compile(r"(stock|estoque|availability)", re.I)}):
            valor = self._texto_limpo(tag.get_text(" ", strip=True)).lower()
            if any(termo in valor for termo in ["sem estoque", "indisponível", "indisponivel", "esgotado"]):
                return 0
            if any(termo in valor for termo in ["em estoque", "disponível", "disponivel"]):
                return 1

        return 0

    def _url_parece_produto(self, url: str) -> bool:
        url_l = (url or "").lower()

        if any(token in url_l for token in ["/produto/", "/produtos/", "/product/", "/p/"]):
            return True

        if re.search(r"/[a-z0-9\-]+-\d{3,}", url_l):
            return True

        if any(token in url_l for token in ["sku=", "produto=", "product_id=", "idproduto=", "id_produto="]):
            return True

        return False

    def _limpar_url(self, url: str) -> str:
        url = self._normalizar_url(url)
        if not url:
            return ""
        # remove fragmento para ajudar na deduplicação
        return url.split("#")[0].strip()

    def _hostname(self, url: str) -> str:
        try:
            return (urlparse(self._normalizar_url(url)).hostname or "").strip().lower()
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # PADRONIZAÇÃO
    # ------------------------------------------------------------------
    def _padronizar(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        resultado: List[Dict[str, Any]] = []

        for p in produtos:
            if not isinstance(p, dict):
                continue

            nome = self._texto_limpo(p.get("nome"))
            url_produto = self._texto_limpo(p.get("url_produto"))
            sku = self._texto_limpo(p.get("sku"))
            marca = self._texto_limpo(p.get("marca"))
            categoria = self._texto_limpo(p.get("categoria"))
            gtin = self._texto_limpo(p.get("gtin"))
            descricao = self._texto_limpo(p.get("descricao"))

            estoque = self._normalizar_estoque(p.get("estoque"))
            preco = self._normalizar_preco(p.get("preco"))
            imagens = self._normalizar_imagens(p.get("imagens"))

            if not nome and not url_produto:
                continue

            resultado.append(
                {
                    "url_produto": url_produto,
                    "nome": nome,
                    "sku": sku,
                    "marca": marca,
                    "categoria": categoria,
                    "estoque": estoque,
                    "preco": preco,
                    "gtin": gtin,
                    "descricao": descricao,
                    "imagens": imagens,
                }
            )

        return self._deduplicar(resultado)

    def _normalizar_estoque(self, valor: Any) -> int:
        if valor is None:
            return 0

        if isinstance(valor, bool):
            return int(valor)

        if isinstance(valor, (int, float)):
            return max(int(valor), 0)

        texto = self._texto_limpo(valor).lower()
        if not texto:
            return 0

        if any(
            termo in texto
            for termo in [
                "esgotado",
                "sem estoque",
                "indisponível",
                "indisponivel",
                "zerado",
                "out of stock",
            ]
        ):
            return 0

        match = re.search(r"(\d+)", texto)
        if match:
            try:
                return max(int(match.group(1)), 0)
            except Exception:
                return 0

        if any(
            termo in texto
            for termo in [
                "disponível",
                "disponivel",
                "em estoque",
                "available",
                "in stock",
            ]
        ):
            return 1

        return 0

    def _normalizar_preco(self, valor: Any) -> float:
        if valor is None:
            return 0.0

        if isinstance(valor, (int, float)):
            return float(valor)

        texto = self._texto_limpo(valor)
        if not texto:
            return 0.0

        texto = texto.replace("R$", "").replace("r$", "").strip()
        texto = re.sub(r"[^\d,.\-]", "", texto)

        if texto.count(",") > 0 and texto.count(".") > 0:
            texto = texto.replace(".", "").replace(",", ".")
        elif texto.count(",") > 0:
            texto = texto.replace(",", ".")

        try:
            return float(texto)
        except Exception:
            return 0.0

    def _normalizar_imagens(self, imagens: Any) -> str:
        if not imagens:
            return ""

        if isinstance(imagens, list):
            itens = imagens
        else:
            bruto = str(imagens).replace(";", "|").replace(",", "|")
            itens = bruto.split("|")

        lista_final: List[str] = []
        vistos = set()

        for item in itens:
            valor = self._texto_limpo(item)
            if not valor:
                continue
            if valor in vistos:
                continue
            vistos.add(valor)
            lista_final.append(valor)

        return "|".join(lista_final)

    def _texto_limpo(self, valor: Any) -> str:
        texto = str(valor or "").strip()
        if texto.lower() in {"nan", "none", "null"}:
            return ""
        return texto

    def _normalizar_url(self, url: str) -> str:
        texto = self._texto_limpo(url)
        if not texto:
            return ""
        if not texto.startswith(("http://", "https://")):
            texto = f"https://{texto}"
        return texto

    def _filtrar_kwargs_fornecedor(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        removidos = {
            "base_url",
            "diagnostico",
            "termo",
            "limite_links",
        }
        return {k: v for k, v in kwargs.items() if k not in removidos}

    def _deduplicar(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        vistos = set()
        resultado: List[Dict[str, Any]] = []

        for p in produtos:
            chave = (
                self._texto_limpo(p.get("url_produto"))
                or self._texto_limpo(p.get("sku"))
                or self._texto_limpo(p.get("gtin"))
                or self._texto_limpo(p.get("nome"))
            )

            if not chave:
                continue
            if chave in vistos:
                continue

            vistos.add(chave)
            resultado.append(p)

        return resultado

    def _log(self, mensagem: str) -> None:
        try:
            print(mensagem)
        except Exception:
            pass

    def para_dataframe(self, produtos: List[Dict[str, Any]]) -> pd.DataFrame:
        produtos = self._padronizar(produtos)

        if not produtos:
            return pd.DataFrame(
                columns=[
                    "url_produto",
                    "nome",
                    "sku",
                    "marca",
                    "categoria",
                    "estoque",
                    "preco",
                    "gtin",
                    "descricao",
                    "imagens",
                ]
            )

        df = pd.DataFrame(produtos).fillna("")

        if "estoque" in df.columns:
            df["estoque"] = df["estoque"].apply(self._normalizar_estoque)

        if "preco" in df.columns:
            df["preco"] = df["preco"].apply(self._normalizar_preco)

        if "imagens" in df.columns:
            df["imagens"] = df["imagens"].apply(self._normalizar_imagens)

        return df

    def _diagnostico_basico(
        self,
        *,
        url: str,
        fornecedor: Any,
        produtos: List[Dict[str, Any]],
        auth_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        nome_fornecedor = ""
        try:
            nome_fornecedor = str(getattr(fornecedor, "nome", "") or "").strip()
        except Exception:
            nome_fornecedor = ""

        fonte = "fallback_interno"
        nome_fornecedor_l = nome_fornecedor.lower()

        if nome_fornecedor_l.startswith("fornecedor gen"):
            fonte = "generic_supplier"
        elif "mega center" in nome_fornecedor_l:
            fonte = "fornecedor_especifico"
        elif "atacadum" in nome_fornecedor_l:
            fonte = "fornecedor_especifico"

        df_diag = pd.DataFrame(produtos).copy() if produtos else pd.DataFrame()
        if not df_diag.empty:
            df_diag["valido"] = True

        return {
            "url": url,
            "fornecedor": nome_fornecedor or "Fornecedor Genérico",
            "fonte_descoberta": fonte,
            "diagnostico_df": df_diag,
            "total_descobertos": int(len(produtos)),
            "total_validos": int(len(produtos)),
            "total_rejeitados": 0,
            "login_status": {
                "status": "session_ready" if bool((auth_context or {}).get("session_ready")) else "publico",
                "mensagem": (
                    "Sessão autenticada aplicada à busca."
                    if bool((auth_context or {}).get("session_ready"))
                    else "Busca pública."
                ),
            },
        }

    def _aplicar_diagnostico_streamlit(self, diagnostico: Dict[str, Any]) -> None:
        if st is None:
            return

        try:
            st.session_state["site_busca_diagnostico_df"] = diagnostico.get("diagnostico_df", pd.DataFrame())
            st.session_state["site_busca_diagnostico_total_descobertos"] = int(
                diagnostico.get("total_descobertos", 0) or 0
            )
            st.session_state["site_busca_diagnostico_total_validos"] = int(
                diagnostico.get("total_validos", 0) or 0
            )
            st.session_state["site_busca_diagnostico_total_rejeitados"] = int(
                diagnostico.get("total_rejeitados", 0) or 0
            )
            st.session_state["site_busca_login_status"] = diagnostico.get("login_status", {}) or {}
            st.session_state["site_busca_fonte_descoberta"] = str(
                diagnostico.get("fonte_descoberta", "") or ""
            ).strip()
        except Exception:
            pass


_site_agent_instance: Optional[SiteAgent] = None


def get_site_agent() -> SiteAgent:
    global _site_agent_instance
    if _site_agent_instance is None:
        _site_agent_instance = SiteAgent()
    return _site_agent_instance


def buscar_produtos_site(url: str, **kwargs) -> List[Dict[str, Any]]:
    agent = get_site_agent()
    return agent.executar(url, **kwargs)


def buscar_produtos_site_df(url: str, **kwargs) -> pd.DataFrame:
    agent = get_site_agent()
    return agent.buscar_dataframe(base_url=url, **kwargs)


def buscar_produtos_site_com_gpt(
    *,
    base_url: str,
    termo: str = "",
    limite_links: Optional[int] = None,
    diagnostico: bool = False,
    auth_context: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> pd.DataFrame:
    agent = get_site_agent()

    kwargs_execucao = dict(kwargs)
    if limite_links is not None and "limite" not in kwargs_execucao:
        kwargs_execucao["limite"] = limite_links

    return agent.buscar_dataframe(
        base_url=base_url,
        diagnostico=diagnostico,
        auth_context=auth_context,
        **kwargs_execucao,
    )
