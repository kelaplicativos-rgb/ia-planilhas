"""
FORNECEDOR OBA OBA MIX — BLINGFIX

Responsável por:
- Registrar ObaObaMixSupplier no registry.
- Detectar URLs da Oba Oba Mix.
- Evitar que o fornecedor fique vazio/quebrado.
- Tentar extração HTTP pública quando houver HTML acessível.
- Não inventar produto, estoque, preço ou quantidade.
- Retornar lista vazia de forma segura quando exigir login/captcha/painel privado.

Observação:
A Oba Oba Mix pode operar em área autenticada com login/captcha.
Quando o conteúdo estiver protegido, este scraper não força bypass.
Ele apenas informa limitação via campo interno e permite fallback/controladoria do fluxo.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.suppliers.base import SupplierBase


class ObaObaMixSupplier(SupplierBase):
    nome = "Oba Oba Mix"

    dominio = [
        "obaobamix.com.br",
        "www.obaobamix.com.br",
        "app.obaobamix.com.br",
    ]

    DEFAULT_HEADERS = {
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

    def fetch(self, url: str, limite: int = 300, **kwargs) -> List[Dict[str, Any]]:
        """
        Busca produtos da Oba Oba Mix.

        Fluxo seguro:
        1. Normaliza URL.
        2. Baixa HTML público.
        3. Se detectar login/captcha/painel privado, retorna vazio sem quebrar.
        4. Tenta JSON-LD Product.
        5. Tenta cards/listagem pública.
        6. Deduplica e valida pelo contrato do SupplierBase.
        """
        url = self._normalizar_url(url)
        if not url:
            return []

        limite = self._int_seguro(limite, 300)
        auth_context = kwargs.get("auth_context") if isinstance(kwargs.get("auth_context"), dict) else None

        html = self._get_html(url, auth_context=auth_context)
        if not html:
            return []

        if self._conteudo_protegido(html, url):
            return []

        soup = BeautifulSoup(html, "html.parser")

        produtos: List[Dict[str, Any]] = []
        produtos.extend(self._extrair_jsonld(soup, url))

        if len(produtos) < limite:
            produtos.extend(self._extrair_cards_publicos(soup, url, limite=limite))

        produtos = self._deduplicar(produtos[:limite])
        return self.validar_produtos(produtos)

    def _get_html(self, url: str, auth_context: Dict[str, Any] | None = None) -> str:
        session = requests.Session()
        session.headers.update(self.DEFAULT_HEADERS)

        if isinstance(auth_context, dict):
            headers = auth_context.get("headers", {}) or {}
            if isinstance(headers, dict):
                for chave, valor in headers.items():
                    chave_txt = self._clean(chave)
                    valor_txt = self._clean(valor)
                    if chave_txt and valor_txt:
                        session.headers[chave_txt] = valor_txt

            cookies = auth_context.get("cookies", []) or []
            if isinstance(cookies, list):
                for cookie in cookies:
                    if not isinstance(cookie, dict):
                        continue

                    nome = self._clean(cookie.get("name"))
                    valor = self._clean(cookie.get("value"))
                    dominio = self._clean(cookie.get("domain"))
                    caminho = self._clean(cookie.get("path")) or "/"

                    if nome and valor:
                        try:
                            session.cookies.set(nome, valor, domain=dominio or None, path=caminho)
                        except Exception:
                            try:
                                session.cookies.set(nome, valor)
                            except Exception:
                                pass

        for candidate in self._candidate_urls(url):
            try:
                response = session.get(candidate, timeout=25, allow_redirects=True)
                if response.status_code >= 400:
                    continue

                texto = response.text or ""
                if not texto.strip():
                    continue

                content_type = str(response.headers.get("Content-Type", "") or "").lower()
                if "text/html" not in content_type and "<html" not in texto.lower():
                    continue

                return texto
            except Exception:
                continue

        return ""

    def _candidate_urls(self, url: str) -> List[str]:
        url = self._normalizar_url(url)
        if not url:
            return []

        parsed = urlparse(url)
        host = parsed.netloc
        path = parsed.path or "/"
        query = f"?{parsed.query}" if parsed.query else ""

        candidatos = []

        def add(value: str) -> None:
            value = self._clean(value)
            if value and value not in candidatos:
                candidatos.append(value)

        add(f"{parsed.scheme}://{host}{path}{query}")

        if host.startswith("www."):
            add(f"{parsed.scheme}://{host[4:]}{path}{query}")
        else:
            add(f"{parsed.scheme}://www.{host}{path}{query}")

        if parsed.scheme == "https":
            add(f"http://{host}{path}{query}")
            if host.startswith("www."):
                add(f"http://{host[4:]}{path}{query}")
            else:
                add(f"http://www.{host}{path}{query}")

        return candidatos

    def _conteudo_protegido(self, html: str, url: str) -> bool:
        texto = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True).lower()
        url_l = self._clean(url).lower()

        sinais_login = [
            "fazer login",
            "entrar",
            "senha",
            "e-mail",
            "email",
            "captcha",
            "recaptcha",
            "hcaptcha",
            "área restrita",
            "area restrita",
            "painel administrativo",
            "admin/products",
            "login",
        ]

        if "/login" in url_l or "/admin" in url_l:
            return True

        encontrados = sum(1 for sinal in sinais_login if sinal in texto)
        sinais_produto = any(
            sinal in texto
            for sinal in [
                "comprar",
                "adicionar ao carrinho",
                "produto",
                "preço",
                "preco",
                "r$",
                "sku",
                "estoque",
            ]
        )

        return encontrados >= 2 and not sinais_produto

    def _extrair_jsonld(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        produtos: List[Dict[str, Any]] = []

        for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
            bruto = script.string or script.get_text(" ", strip=True) or ""
            bruto = bruto.strip()
            if not bruto:
                continue

            try:
                data = json.loads(bruto)
            except Exception:
                continue

            for item in self._iter_jsonld(data):
                produto = self._produto_jsonld(item, base_url)
                if produto:
                    produtos.append(produto)

        return produtos

    def _iter_jsonld(self, data: Any) -> List[Dict[str, Any]]:
        encontrados: List[Dict[str, Any]] = []

        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                tipo = obj.get("@type")
                if tipo == "Product" or (isinstance(tipo, list) and "Product" in tipo):
                    encontrados.append(obj)

                for valor in obj.values():
                    if isinstance(valor, (dict, list)):
                        walk(valor)

            elif isinstance(obj, list):
                for valor in obj:
                    walk(valor)

        walk(data)
        return encontrados

    def _produto_jsonld(self, item: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        if not isinstance(item, dict):
            return {}

        offers = item.get("offers")
        if isinstance(offers, list) and offers:
            offers = offers[0]

        preco = ""
        estoque = 0

        if isinstance(offers, dict):
            preco = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice") or ""
            availability = self._clean(offers.get("availability")).lower()
            if "outofstock" in availability or "soldout" in availability:
                estoque = 0
            elif "instock" in availability or "in stock" in availability:
                estoque = 1

        imagens = item.get("image", [])
        if isinstance(imagens, str):
            imagens = [imagens]
        elif not isinstance(imagens, list):
            imagens = []

        brand = item.get("brand")
        marca = ""
        if isinstance(brand, dict):
            marca = self._clean(brand.get("name"))
        elif isinstance(brand, str):
            marca = self._clean(brand)

        gtin = (
            item.get("gtin14")
            or item.get("gtin13")
            or item.get("gtin12")
            or item.get("gtin8")
            or item.get("gtin")
            or ""
        )

        return {
            "fornecedor": self.nome,
            "url_produto": self._normalizar_url(item.get("url") or base_url),
            "nome": self._clean(item.get("name")),
            "sku": self._clean(item.get("sku") or item.get("mpn")),
            "marca": marca,
            "categoria": self._clean(item.get("category")),
            "preco": self._to_float(preco),
            "estoque": estoque,
            "gtin": self._digits(gtin),
            "descricao": self._clean(item.get("description")),
            "imagens": [self._absolute(base_url, img) for img in imagens if self._clean(img)],
        }

    def _extrair_cards_publicos(
        self,
        soup: BeautifulSoup,
        base_url: str,
        limite: int = 300,
    ) -> List[Dict[str, Any]]:
        produtos: List[Dict[str, Any]] = []
        seletores = [
            "[class*=product]",
            "[class*=produto]",
            "[class*=card]",
            "[class*=item]",
            "article",
            "li",
        ]

        elementos = []
        for seletor in seletores:
            for el in soup.select(seletor):
                if el not in elementos:
                    elementos.append(el)

        for el in elementos:
            if len(produtos) >= limite:
                break

            texto = el.get_text(" ", strip=True)
            texto_limpo = self._clean(texto)

            if len(texto_limpo) < 12:
                continue

            if self._parece_lixo(texto_limpo):
                continue

            link = ""
            link_tag = el.find("a", href=True)
            if link_tag:
                link = self._absolute(base_url, link_tag.get("href"))

            if not link:
                continue

            if not self._url_parece_produto(link) and len(texto_limpo) < 30:
                continue

            nome = self._extrair_nome_card(el, texto_limpo)
            preco = self._extrair_preco_texto(texto_limpo)
            estoque = self._extrair_estoque_texto(texto_limpo)
            sku = self._extrair_sku_texto(texto_limpo)
            gtin = self._extrair_gtin_texto(texto_limpo)
            imagens = self._extrair_imagens_card(el, base_url)

            produto = {
                "fornecedor": self.nome,
                "url_produto": link,
                "nome": nome,
                "sku": sku,
                "marca": "",
                "categoria": "",
                "preco": preco,
                "estoque": estoque,
                "gtin": gtin,
                "descricao": texto_limpo[:1500],
                "imagens": imagens,
            }

            produtos.append(produto)

        return produtos

    def _extrair_nome_card(self, el, fallback: str) -> str:
        for seletor in ["h1", "h2", "h3", ".title", ".titulo", "[class*=title]", "[class*=titulo]"]:
            node = el.select_one(seletor)
            if node:
                nome = self._clean(node.get_text(" ", strip=True))
                if len(nome) >= 3:
                    return nome[:220]

        linhas = [self._clean(x) for x in fallback.split("  ") if self._clean(x)]
        if linhas:
            return linhas[0][:220]

        return fallback[:220]

    def _extrair_preco_texto(self, texto: str) -> float:
        match = re.search(r"R\$\s*([\d\.,]+)", texto or "", re.I)
        if not match:
            return 0.0
        return self._to_float(match.group(1))

    def _extrair_estoque_texto(self, texto: str) -> int:
        texto_l = self._clean(texto).lower()

        if any(
            termo in texto_l
            for termo in [
                "sem estoque",
                "esgotado",
                "indisponível",
                "indisponivel",
                "zerado",
                "out of stock",
            ]
        ):
            return 0

        patterns = [
            r"(?:estoque|quantidade|dispon[ií]vel|saldo)[^0-9]{0,25}(\d+)",
            r"(\d+)\s*(?:unidades|unidade|itens|item|peças|pecas)\s*(?:em estoque|dispon[ií]vel)",
        ]

        for pattern in patterns:
            match = re.search(pattern, texto_l, re.I)
            if match:
                try:
                    return max(int(match.group(1)), 0)
                except Exception:
                    pass

        if any(termo in texto_l for termo in ["em estoque", "disponível", "disponivel", "comprar"]):
            return 1

        return 0

    def _extrair_sku_texto(self, texto: str) -> str:
        match = re.search(r"(?:sku|c[oó]digo|cod\.?|refer[êe]ncia|ref\.?)\W{0,12}([a-zA-Z0-9._/-]+)", texto or "", re.I)
        return self._clean(match.group(1))[:80] if match else ""

    def _extrair_gtin_texto(self, texto: str) -> str:
        match = re.search(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b", texto or "")
        return match.group(1) if match else ""

    def _extrair_imagens_card(self, el, base_url: str) -> List[str]:
        imagens: List[str] = []

        for img in el.find_all("img"):
            src = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-lazy")
                or img.get("data-original")
            )
            link = self._absolute(base_url, src)
            if link and self._imagem_valida(link):
                imagens.append(link)

        return list(dict.fromkeys(imagens))[:8]

    def _url_parece_produto(self, url: str) -> bool:
        value = self._clean(url).lower()

        if not value:
            return False

        bloqueios = [
            "/login",
            "/admin",
            "/checkout",
            "/cart",
            "/carrinho",
            "/account",
            "/conta",
            "whatsapp:",
            "mailto:",
            "tel:",
            "#",
        ]

        if any(item in value for item in bloqueios):
            return False

        sinais = [
            "/produto",
            "/produtos",
            "/product",
            "/products",
            "/p/",
            "/item",
            ".html",
            ".htm",
        ]

        if any(item in value for item in sinais):
            return True

        slug = urlparse(value).path.rstrip("/").split("/")[-1]
        return len(slug) >= 12 and any(ch.isdigit() for ch in slug)

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

        return not any(item in value for item in bloqueios)

    def _parece_lixo(self, texto: str) -> bool:
        texto_l = self._clean(texto).lower()
        lixo = [
            "entrar",
            "login",
            "senha",
            "esqueci minha senha",
            "criar conta",
            "política de privacidade",
            "politica de privacidade",
            "termos de uso",
            "cookies",
            "menu",
        ]
        return any(item in texto_l for item in lixo) and "r$" not in texto_l

    def _deduplicar(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        vistos = set()
        resultado = []

        for produto in produtos or []:
            if not isinstance(produto, dict):
                continue

            key = (
                self._clean(produto.get("url_produto"))
                or self._clean(produto.get("sku"))
                or self._clean(produto.get("nome")).lower()
            )

            if not key or key in vistos:
                continue

            vistos.add(key)
            resultado.append(produto)

        return resultado

    def _normalizar_url(self, valor: Any) -> str:
        texto = self._clean(valor)
        if not texto:
            return ""

        if not texto.startswith(("http://", "https://")):
            texto = f"https://{texto}"

        return texto.split("#", 1)[0].strip()

    def _absolute(self, base_url: str, valor: Any) -> str:
        texto = self._clean(valor)
        if not texto:
            return ""
        return urljoin(self._normalizar_url(base_url), texto)

    def _clean(self, valor: Any) -> str:
        texto = str(valor or "").strip()
        return "" if texto.lower() in {"none", "null", "nan"} else texto

    def _digits(self, valor: Any) -> str:
        return re.sub(r"\D+", "", str(valor or ""))

    def _to_float(self, valor: Any) -> float:
        texto = self._clean(valor)
        if not texto:
            return 0.0

        texto = texto.replace("R$", "").replace("r$", "").strip()
        texto = re.sub(r"[^0-9,.\-]", "", texto)

        if "," in texto and "." in texto:
            texto = texto.replace(".", "").replace(",", ".")
        elif "," in texto:
            texto = texto.replace(",", ".")

        try:
            return float(texto)
        except Exception:
            return 0.0

    def _int_seguro(self, valor: Any, padrao: int) -> int:
        try:
            return int(valor)
        except Exception:
            return padrao
