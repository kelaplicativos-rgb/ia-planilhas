from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Set
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.suppliers.base import SupplierBase


class MegaCenterSupplier(SupplierBase):
    nome = "Mega Center Eletrônicos"

    dominio = [
        "megacentereletronicos.com.br",
        "www.megacentereletronicos.com.br",
        "mega-center-eletronicos.stoqui.shop",
        "stoqui.shop",
    ]

    HEADERS = {
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

    def fetch(self, url: str, **kwargs) -> List[Dict[str, Any]]:
        url = self._normalizar_url(url)
        if not url:
            return []

        limite = int(kwargs.get("limite", 300) or 300)
        max_paginas = int(kwargs.get("max_paginas", 40) or 40)
        max_workers = int(kwargs.get("max_workers", 8) or 8)
        max_workers = max(2, min(max_workers, 10))

        session = requests.Session()
        session.headers.update(self.HEADERS)

        links = []
        links.extend(self._descobrir_links_sitemap(session, url, limite=limite))
        links.extend(self._descobrir_links_pagina(session, url, max_paginas=max_paginas, limite=limite))

        links = self._dedup_urls(links)

        if not links:
            html, final_url = self._get_html(session, url)
            if html and self._pagina_parece_produto(html, final_url):
                links = [final_url]

        produtos: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futuros = {
                executor.submit(self._extrair_produto, session, link): link
                for link in links[:limite]
            }

            for futuro in as_completed(futuros):
                try:
                    produto = futuro.result()
                    if produto:
                        produtos.append(produto)
                except Exception:
                    continue

        return self.validar_produtos(produtos)

    def _get_html(self, session: requests.Session, url: str, timeout: int = 25) -> tuple[str, str]:
        url = self._normalizar_url(url)
        if not url:
            return "", ""

        for candidate in self._candidate_urls(url):
            try:
                resp = session.get(candidate, timeout=timeout, allow_redirects=True)
                if resp.status_code >= 400:
                    continue

                html = resp.text or ""
                if "<html" not in html.lower() and "<!doctype html" not in html.lower():
                    continue

                return html[:1_200_000], str(resp.url)
            except Exception:
                continue

        return "", url

    def _descobrir_links_sitemap(self, session: requests.Session, base_url: str, limite: int) -> List[str]:
        encontrados: List[str] = []
        visitados: Set[str] = set()
        fila = self._urls_sitemap(base_url)

        while fila and len(encontrados) < limite:
            sm_url = fila.pop(0)
            if sm_url in visitados:
                continue

            visitados.add(sm_url)

            try:
                resp = session.get(sm_url, timeout=25, allow_redirects=True)
                texto = resp.text or ""
            except Exception:
                continue

            if not texto:
                continue

            sitemaps, urls = self._parse_sitemap(texto)

            for sm in sitemaps:
                if sm not in visitados and sm not in fila:
                    fila.append(sm)

            for link in urls:
                link = self._limpar_url(link)
                if self._mesmo_dominio(base_url, link) and self._url_parece_produto(link):
                    encontrados.append(link)

                if len(encontrados) >= limite:
                    break

        return self._dedup_urls(encontrados)

    def _urls_sitemap(self, base_url: str) -> List[str]:
        parsed = urlparse(self._normalizar_url(base_url))
        raiz = f"{parsed.scheme}://{parsed.netloc}"

        return self._dedup_urls(
            [
                f"{raiz}/sitemap.xml",
                f"{raiz}/sitemap_index.xml",
                f"{raiz}/sitemap-products.xml",
                f"{raiz}/product-sitemap.xml",
                f"{raiz}/produtos-sitemap.xml",
                f"{raiz}/sitemap-produtos.xml",
                f"{raiz}/robots.txt",
            ]
        )

    def _parse_sitemap(self, texto: str) -> tuple[List[str], List[str]]:
        texto = str(texto or "").strip()
        sitemaps: List[str] = []
        urls: List[str] = []

        if not texto:
            return sitemaps, urls

        if texto.lower().startswith("user-agent") or "sitemap:" in texto.lower():
            for linha in texto.splitlines():
                if linha.strip().lower().startswith("sitemap:"):
                    link = linha.split(":", 1)[1].strip()
                    if link:
                        sitemaps.append(link)
            return sitemaps, urls

        try:
            root = ET.fromstring(texto)
        except Exception:
            bruto = re.findall(r"https?://[^\s<>'\"]+", texto)
            return [], [self._limpar_url(u) for u in bruto if u]

        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}", 1)[0] + "}"

        if root.tag.endswith("sitemapindex"):
            for loc in root.findall(f".//{ns}loc"):
                valor = self._clean(loc.text)
                if valor:
                    sitemaps.append(valor)

        if root.tag.endswith("urlset"):
            for loc in root.findall(f".//{ns}loc"):
                valor = self._clean(loc.text)
                if valor:
                    urls.append(valor)

        return sitemaps, urls

    def _descobrir_links_pagina(
        self,
        session: requests.Session,
        url: str,
        max_paginas: int,
        limite: int,
    ) -> List[str]:
        encontrados: List[str] = []
        visitadas: Set[str] = set()
        fila: List[str] = [url]

        while fila and len(visitadas) < max_paginas and len(encontrados) < limite:
            pagina = self._normalizar_url(fila.pop(0))
            if not pagina or pagina in visitadas:
                continue

            visitadas.add(pagina)

            html, final_url = self._get_html(session, pagina)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            if self._pagina_parece_produto(html, final_url):
                encontrados.append(final_url)

            for link in self._extrair_links(soup, final_url):
                if not self._mesmo_dominio(url, link):
                    continue

                if self._url_parece_produto(link):
                    encontrados.append(link)
                elif self._url_parece_categoria(link):
                    if link not in visitadas and link not in fila:
                        fila.append(link)

                if len(encontrados) >= limite:
                    break

            for pag in self._links_paginacao(soup, final_url):
                if pag not in visitadas and pag not in fila:
                    fila.append(pag)

        return self._dedup_urls(encontrados)

    def _extrair_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        links: List[str] = []

        for tag in soup.find_all(["a", "button"], href=True):
            href = self._clean(tag.get("href"))
            link = self._limpar_url(urljoin(base_url, href))
            if link and not self._url_ruim(link):
                links.append(link)

        for attr in ["data-href", "data-url"]:
            for tag in soup.find_all(attrs={attr: True}):
                href = self._clean(tag.get(attr))
                link = self._limpar_url(urljoin(base_url, href))
                if link and not self._url_ruim(link):
                    links.append(link)

        return self._dedup_urls(links)

    def _links_paginacao(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        links: List[str] = []

        seletores = [
            "a[rel='next']",
            "link[rel='next']",
            ".pagination a",
            ".paginacao a",
            "[class*=pagination] a",
            "[class*=paginacao] a",
            "a[href*='page=']",
            "a[href*='pagina=']",
            "a[href*='/page/']",
            "a[href*='/pagina/']",
        ]

        for seletor in seletores:
            for node in soup.select(seletor):
                href = self._clean(node.get("href"))
                link = self._limpar_url(urljoin(base_url, href))
                if link and not self._url_ruim(link):
                    links.append(link)

        return self._dedup_urls(links)

    def _extrair_produto(self, session: requests.Session, url: str) -> Dict[str, Any]:
        html, final_url = self._get_html(session, url)
        if not html:
            return {}

        soup = BeautifulSoup(html, "html.parser")
        texto = soup.get_text(" ", strip=True)

        jsonld = self._jsonld_produto(soup)

        nome = (
            self._clean(jsonld.get("name"))
            or self._meta(soup, "og:title")
            or self._extrair_nome(soup)
        )

        descricao = (
            self._clean(jsonld.get("description"))
            or self._meta(soup, "description")
            or self._extrair_descricao(soup)
        )

        preco = (
            self._preco_jsonld(jsonld)
            or self._meta(soup, "product:price:amount")
            or self._extrair_preco_texto(texto)
        )

        sku = (
            self._clean(jsonld.get("sku"))
            or self._clean(jsonld.get("mpn"))
            or self._extrair_sku(texto, final_url)
        )

        gtin = self._extrair_gtin(jsonld, texto)
        marca = self._extrair_marca(jsonld, texto, nome)
        categoria = self._extrair_categoria(jsonld, soup)
        estoque, estoque_origem = self._extrair_estoque(jsonld, texto)
        imagens = self._extrair_imagens(jsonld, soup, final_url)

        return {
            "fornecedor": self.nome,
            "url_produto": final_url,
            "nome": nome,
            "sku": sku,
            "marca": marca,
            "categoria": categoria,
            "preco": self._to_float(preco),
            "estoque": estoque,
            "quantidade": estoque,
            "quantidade_real": estoque if estoque_origem == "quantidade_real" else "",
            "estoque_origem": estoque_origem,
            "gtin": gtin,
            "descricao": descricao,
            "imagens": imagens,
        }

    def _jsonld_produto(self, soup: BeautifulSoup) -> Dict[str, Any]:
        for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
            raw = script.string or script.get_text(" ", strip=True) or ""
            if not raw:
                continue

            try:
                data = json.loads(raw)
            except Exception:
                continue

            found = self._buscar_product(data)
            if found:
                return found

        return {}

    def _buscar_product(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, list):
            for item in data:
                found = self._buscar_product(item)
                if found:
                    return found

        if isinstance(data, dict):
            tipo = data.get("@type")
            if tipo == "Product" or (isinstance(tipo, list) and "Product" in tipo):
                return data

            if "@graph" in data:
                found = self._buscar_product(data.get("@graph"))
                if found:
                    return found

            for value in data.values():
                if isinstance(value, (dict, list)):
                    found = self._buscar_product(value)
                    if found:
                        return found

        return {}

    def _preco_jsonld(self, jsonld: Dict[str, Any]) -> Any:
        offers = jsonld.get("offers") if isinstance(jsonld, dict) else {}

        if isinstance(offers, list) and offers:
            offers = offers[0]

        if isinstance(offers, dict):
            return offers.get("price") or offers.get("lowPrice") or offers.get("highPrice")

        return ""

    def _extrair_estoque(self, jsonld: Dict[str, Any], texto: str) -> tuple[int, str]:
        texto_l = self._clean(texto).lower()

        offers = jsonld.get("offers") if isinstance(jsonld, dict) else {}
        if isinstance(offers, list) and offers:
            offers = offers[0]

        availability = ""
        inventory_level = ""

        if isinstance(offers, dict):
            availability = self._clean(offers.get("availability")).lower()
            inventory_level = self._clean(
                offers.get("inventoryLevel")
                or offers.get("inventory_level")
                or offers.get("inventory")
            )

        zero_terms = [
            "sem estoque",
            "sem disponibilidade",
            "esgotado",
            "indisponível",
            "indisponivel",
            "produto indisponível",
            "produto indisponivel",
            "avise-me",
            "avise me",
            "out of stock",
            "soldout",
            "sold out",
            "zerado",
            "fora de estoque",
        ]

        if any(x in availability for x in ["outofstock", "soldout", "discontinued"]):
            return 0, "zerado_availability"

        if any(term in texto_l for term in zero_terms):
            return 0, "zerado_texto"

        if inventory_level:
            match = re.search(r"\d+", inventory_level)
            if match:
                return max(int(match.group(0)), 0), "quantidade_real"

        patterns = [
            r"(?:estoque|quantidade|dispon[ií]vel|saldo)\s*(?:atual|total)?[^0-9]{0,35}(\d+)",
            r"(\d+)\s*(?:unidades|unidade|itens|item|peças|pecas)\s*(?:em estoque|dispon[ií]ve(?:l|is))",
            r"(?:restam|resta)\s*(\d+)",
            r"(?:qtd|qtde|quant\.)[^0-9]{0,20}(\d+)",
            r"(?:em estoque)[:\s-]{0,10}(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, texto_l, re.I)
            if match:
                try:
                    return max(int(match.group(1)), 0), "quantidade_real"
                except Exception:
                    pass

        positive_terms = [
            "em estoque",
            "disponível",
            "disponivel",
            "pronta entrega",
            "comprar",
            "adicionar ao carrinho",
            "instock",
            "in stock",
        ]

        if any(x in availability for x in ["instock", "in stock"]):
            return 1, "status_positivo_sem_quantidade"

        if any(term in texto_l for term in positive_terms):
            return 1, "status_positivo_sem_quantidade"

        return 0, "nao_detectado"

    def _extrair_sku(self, texto: str, url: str) -> str:
        patterns = [
            r"(?:sku|c[oó]digo|cod\.?|refer[êe]ncia|ref\.?)\W{0,12}([a-zA-Z0-9._/-]+)",
            r"\bID\W{0,8}([a-zA-Z0-9._/-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, texto or "", re.I)
            if match:
                sku = self._clean(match.group(1))
                if len(sku) >= 2:
                    return sku[:80]

        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        match = re.search(r"(\d{3,})", slug)
        return match.group(1) if match else ""

    def _extrair_gtin(self, jsonld: Dict[str, Any], texto: str) -> str:
        for key in ["gtin14", "gtin13", "gtin12", "gtin8", "gtin", "ean"]:
            value = self._digits(jsonld.get(key)) if isinstance(jsonld, dict) else ""
            if len(value) in {8, 12, 13, 14}:
                return value

        match = re.search(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b", texto or "")
        return match.group(1) if match else ""

    def _extrair_marca(self, jsonld: Dict[str, Any], texto: str, nome: str) -> str:
        brand = jsonld.get("brand") if isinstance(jsonld, dict) else ""

        if isinstance(brand, dict):
            marca = self._clean(brand.get("name"))
            if marca:
                return marca

        if isinstance(brand, str) and brand.strip():
            return brand.strip()

        match = re.search(r"(?:marca)\W{0,12}([a-zA-Z0-9À-ÿ ._-]{2,40})", texto or "", re.I)
        if match:
            return self._clean(match.group(1))[:60]

        palavras = self._clean(nome).split()
        return palavras[0][:60] if palavras else ""

    def _extrair_categoria(self, jsonld: Dict[str, Any], soup: BeautifulSoup) -> str:
        categoria_json = self._clean(jsonld.get("category")) if isinstance(jsonld, dict) else ""
        if categoria_json:
            return categoria_json

        crumbs: List[str] = []

        for selector in [".breadcrumb a", ".breadcrumbs a", "[class*=breadcrumb] a", "nav a"]:
            for node in soup.select(selector):
                txt = self._clean(node.get_text(" ", strip=True))
                if txt and txt.lower() not in {"home", "início", "inicio"}:
                    crumbs.append(txt)

            if crumbs:
                break

        return " > ".join(dict.fromkeys(crumbs))[:250]

    def _extrair_nome(self, soup: BeautifulSoup) -> str:
        for selector in [
            "h1",
            ".product-title",
            ".product_title",
            "[class*=product][class*=title]",
            ".title",
            "meta[property='og:title']",
        ]:
            node = soup.select_one(selector)
            if node:
                if node.name == "meta":
                    value = self._clean(node.get("content"))
                else:
                    value = self._clean(node.get_text(" ", strip=True))
                if value:
                    return value[:220]

        return ""

    def _extrair_descricao(self, soup: BeautifulSoup) -> str:
        for selector in [
            ".product-description",
            ".descricao",
            ".description",
            "#description",
            "[class*=description]",
            "[class*=descricao]",
        ]:
            node = soup.select_one(selector)
            if node:
                value = self._clean(node.get_text(" ", strip=True))
                if len(value) >= 20:
                    return value[:2000]

        return ""

    def _extrair_preco_texto(self, texto: str) -> float:
        match = re.search(r"R\$\s*([\d\.,]+)", texto or "")
        return self._to_float(match.group(1)) if match else 0.0

    def _extrair_imagens(self, jsonld: Dict[str, Any], soup: BeautifulSoup, base_url: str) -> List[str]:
        imagens: List[str] = []

        raw_json_images = jsonld.get("image") if isinstance(jsonld, dict) else []
        if isinstance(raw_json_images, str):
            raw_json_images = [raw_json_images]

        if isinstance(raw_json_images, list):
            for img in raw_json_images:
                link = self._limpar_url(urljoin(base_url, self._clean(img)))
                if self._imagem_valida(link):
                    imagens.append(link)

        og = soup.select_one("meta[property='og:image']")
        if og:
            link = self._limpar_url(urljoin(base_url, self._clean(og.get("content"))))
            if self._imagem_valida(link):
                imagens.append(link)

        for img in soup.find_all("img"):
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-lazy")
                or img.get("data-original")
                or img.get("data-zoom-image")
            )

            link = self._limpar_url(urljoin(base_url, self._clean(src)))
            if self._imagem_valida(link):
                imagens.append(link)

        return self._dedup_urls(imagens)[:12]

    def _pagina_parece_produto(self, html: str, url: str) -> bool:
        page = (html or "").lower()
        url_l = (url or "").lower()

        sinais = 0

        if self._url_parece_produto(url_l):
            sinais += 2
        if '"@type":"product"' in page or '"@type": "product"' in page:
            sinais += 3
        if "comprar" in page or "adicionar ao carrinho" in page:
            sinais += 1
        if "sku" in page or "código" in page or "codigo" in page:
            sinais += 1
        if re.search(r"r\$\s*\d", page):
            sinais += 1

        return sinais >= 3

    def _url_parece_produto(self, url: str) -> bool:
        value = self._clean(url).lower()

        if not value or self._url_ruim(value):
            return False

        sinais = [
            "/produto/",
            "/produtos/",
            "/product/",
            "/products/",
            "/p/",
            "/item/",
            ".html",
            ".htm",
        ]

        if any(s in value for s in sinais):
            return True

        slug = urlparse(value).path.rstrip("/").split("/")[-1]
        return len(slug) >= 12 and any(ch.isdigit() for ch in slug)

    def _url_parece_categoria(self, url: str) -> bool:
        value = self._clean(url).lower()

        if not value or self._url_ruim(value):
            return False

        sinais = [
            "/categoria",
            "/categorias",
            "/catalogo",
            "/catalog",
            "/collections",
            "/collection",
            "/departamento",
            "/departamentos",
            "/marcas",
            "/marca",
            "page=",
            "pagina=",
            "categoria=",
            "/page/",
            "/pagina/",
        ]

        return any(s in value for s in sinais)

    def _url_ruim(self, url: str) -> bool:
        value = self._clean(url).lower()

        bloqueios = [
            "/login",
            "/conta",
            "/account",
            "/checkout",
            "/cart",
            "/carrinho",
            "/politica",
            "/privacy",
            "/blog",
            "/tag/",
            "/author/",
            "whatsapp:",
            "mailto:",
            "tel:",
            "#",
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif",
            ".pdf",
        ]

        return any(b in value for b in bloqueios)

    def _imagem_valida(self, url: str) -> bool:
        value = self._clean(url).lower()

        if not value.startswith(("http://", "https://")):
            return False

        bloqueios = [
            "logo",
            "icon",
            "sprite",
            "banner",
            "placeholder",
            "avatar",
            "loading",
            "whatsapp",
            "facebook",
            "instagram",
            "youtube",
        ]

        return not any(b in value for b in bloqueios)

    def _normalizar_url(self, url: Any) -> str:
        value = self._clean(url)
        if not value:
            return ""

        if not value.startswith(("http://", "https://")):
            value = f"https://{value}"

        return self._limpar_url(value)

    def _candidate_urls(self, url: str) -> List[str]:
        parsed = urlparse(self._normalizar_url(url))
        host = parsed.netloc
        path = parsed.path or "/"
        query = f"?{parsed.query}" if parsed.query else ""

        urls = [f"{parsed.scheme}://{host}{path}{query}"]

        if host.startswith("www."):
            urls.append(f"{parsed.scheme}://{host[4:]}{path}{query}")
        else:
            urls.append(f"{parsed.scheme}://www.{host}{path}{query}")

        if parsed.scheme == "https":
            urls.append(f"http://{host}{path}{query}")

        return self._dedup_urls(urls)

    def _limpar_url(self, url: Any) -> str:
        value = self._clean(url)
        if not value:
            return ""

        return value.split("#", 1)[0].strip()

    def _mesmo_dominio(self, base_url: str, candidate_url: str) -> bool:
        base_host = urlparse(self._normalizar_url(base_url)).netloc.replace("www.", "").lower()
        cand_host = urlparse(self._normalizar_url(candidate_url)).netloc.replace("www.", "").lower()

        aliases = {
            "megacentereletronicos.com.br",
            "mega-center-eletronicos.stoqui.shop",
            "stoqui.shop",
        }

        if base_host in aliases and cand_host in aliases:
            return True

        return base_host == cand_host or cand_host.endswith(base_host)

    def _meta(self, soup: BeautifulSoup, name: str) -> str:
        selectors = [
            f"meta[property='{name}']",
            f"meta[name='{name}']",
        ]

        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                value = self._clean(node.get("content"))
                if value:
                    return value

        return ""

    def _clean(self, value: Any) -> str:
        text = str(value or "").strip()
        text = re.sub(r"\s+", " ", text)
        return "" if text.lower() in {"none", "null", "nan"} else text

    def _digits(self, value: Any) -> str:
        return re.sub(r"\D+", "", str(value or ""))

    def _to_float(self, value: Any) -> float:
        raw = self._clean(value)
        if not raw:
            return 0.0

        raw = raw.replace("R$", "").replace("r$", "").strip()
        raw = re.sub(r"[^\d,.\-]", "", raw)

        if "," in raw and "." in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            raw = raw.replace(",", ".")

        try:
            return float(raw)
        except Exception:
            return 0.0

    def _dedup_urls(self, urls: List[str]) -> List[str]:
        vistos = set()
        final = []

        for url in urls or []:
            url = self._limpar_url(url)
            if not url or url in vistos:
                continue
            vistos.add(url)
            final.append(url)

        return final

    def _deduplicar_produtos(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        vistos = set()
        final = []

        for produto in produtos or []:
            key = produto.get("url_produto") or produto.get("sku") or produto.get("nome")
            key = self._clean(key).lower()

            if not key or key in vistos:
                continue

            vistos.add(key)
            final.append(produto)

        return final
