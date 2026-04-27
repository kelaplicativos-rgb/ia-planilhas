"""
SITE AGENT (ORQUESTRADOR GLOBAL) — IA ABSURDA PRO

BLINGFIX — crawler destravado + varredura completa + sitemaps completos.

Base respeitada do arquivo enviado:
- mantém SiteAgent
- mantém get_site_agent()
- mantém buscar_produtos_site()
- mantém buscar_produtos_site_df()
- mantém buscar_produtos_site_com_gpt()
- mantém buscar_dataframe(), buscar_produtos() e para_dataframe()

Correções aplicadas:
- remove parada precoce quando encontra poucos produtos
- aceita varrer_site_completo / varredura_completa / site_completo
- aceita sitemap_completo / varrer_sitemap_completo
- sitemap recursivo: sitemapindex, sitemap.xml, robots.txt e sitemaps filhos
- limite 0, None ou -1 significa sem limite
- evita travar com lista vazia ou limite baixo
- corrige marca vindo como nome da loja, exemplo: "Mega Center" / "Mega Center Eletrônicos"
- registra logs também em st.session_state["logs"], quando Streamlit estiver disponível
"""

from __future__ import annotations

import json
import re
import time
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urljoin, urlparse
from xml.etree import ElementTree as ET

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException, SSLError

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

from bling_app_zero.core.suppliers.registry import SupplierRegistry, get_registry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SiteAgent:
    MARCAS_LOJA_BLOQUEADAS = {
        "mega center",
        "mega center eletrônicos",
        "mega center eletronicos",
        "megacenter",
        "megacenter eletrônicos",
        "megacenter eletronicos",
        "loja mega center",
    }

    MARCAS_CONHECIDAS = [
        "Samsung", "Apple", "Motorola", "Xiaomi", "Redmi", "Poco", "Realme",
        "Infinix", "Nokia", "LG", "Sony", "Philips", "Multilaser", "Multi",
        "Positivo", "Lenovo", "Dell", "HP", "Acer", "Asus", "Intelbras",
        "Elgin", "Mondial", "Britânia", "Britania", "Oster", "Cadence",
        "Agratto", "Midea", "Electrolux", "Consul", "Brastemp", "JBL",
        "Amvox", "Tomate", "Knup", "Hrebos", "Sumexr", "Baseus", "Hoco",
        "Inova", "Aiwa", "Pulse", "Aquário", "Aquario", "Elsys", "TCL",
        "AOC", "Philco", "Hayom", "Exbom", "Ugreen", "Geonav", "I2GO",
        "C3Tech", "Leadership", "Goldentec", "Gshield", "Gorila Shield",
        "Kingston", "Sandisk", "Western Digital", "Seagate", "Crucial",
        "Logitech", "Microsoft", "Google", "Amazon", "Epson", "Canon",
        "Brother", "Zebra", "Dymo", "Mercusys", "TP-Link", "Tenda",
        "D-Link", "Huawei", "ZTE", "AMD", "Nvidia", "Radeon", "Geforce",
        "X-Cell", "Pineng", "Kaidi", "Kimaster", "Lelong", "Kross",
        "Roadstar", "First Option",
    ]

    PRODUCT_HINTS = (
        "/produto/", "/produtos/", "/product/", "/products/", "/item/", "/p/"
    )

    CATEGORY_HINTS = (
        "/categoria/", "/categorias/", "/catalogo/", "/catalog/", "/colecao/",
        "/collection/", "/departamento/", "/departamentos/", "/marca/", "/marcas/",
        "/celulares", "/smartphone", "/smartphones", "/relogio", "/smartwatch",
        "/acessorios", "/mais-produtos",
    )

    BAD_LINK_HINTS = (
        "whatsapp", "facebook", "instagram", "youtube", "tiktok", "linkedin",
        "mailto:", "tel:", "/login", "/entrar", "/minha-conta", "/account",
        "/carrinho", "/cart", "/checkout", "/politica", "/privacy", "/termos",
        "/blog", "/noticia", "/contato", "#",
    )

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

        varrer_site_completo = self._bool_compat(
            kwargs.get("varrer_site_completo", kwargs.get("varredura_completa", kwargs.get("site_completo"))),
            default=False,
        )
        sitemap_completo = self._bool_compat(
            kwargs.get("sitemap_completo", kwargs.get("varrer_sitemap_completo")),
            default=varrer_site_completo,
        )

        fornecedor = self._detectar_fornecedor(url)
        produtos: List[Dict[str, Any]] = []
        kwargs_limpos = self._filtrar_kwargs_fornecedor(kwargs)

        if auth_context:
            kwargs_limpos["auth_context"] = auth_context

        preferir_http = self._bool_compat(kwargs.get("preferir_http"), default=True)
        usar_fornecedor = self._bool_compat(kwargs.get("usar_fornecedor"), default=True)
        usar_generico = self._bool_compat(kwargs.get("usar_generico"), default=True)
        fornecedor_eh_generico = self._fornecedor_eh_generico(fornecedor)

        if usar_fornecedor and fornecedor is not None and not fornecedor_eh_generico:
            try:
                self._log(
                    f"[SITE_AGENT] fornecedor específico detectado: "
                    f"{getattr(fornecedor, 'nome', fornecedor.__class__.__name__)} "
                    f"| http_first={preferir_http}"
                )
                produtos = fornecedor.fetch(url, **kwargs_limpos)
                produtos = self._validar_com_fornecedor(fornecedor, produtos)
                if produtos:
                    self._log(f"[SITE_AGENT] fornecedor específico retornou {len(produtos)} produto(s)")
            except Exception as exc:
                self._log(f"[ERRO fornecedor específico] {exc}")

        if not produtos and usar_generico:
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

        # BLINGFIX:
        # Em modo completo, a varredura adaptativa SEMPRE roda, mesmo que fornecedor específico retorne algo.
        # Isso evita coleta parcial do Mega Center e outros fornecedores.
        if varrer_site_completo or sitemap_completo or not produtos:
            self._log("[IA ABSURDA PRO] iniciando varredura adaptativa HTTP-first")
            try:
                produtos_adaptativos = self._executar_varredura_adaptativa(
                    url=url,
                    auth_context=auth_context,
                    kwargs=kwargs,
                )

                if varrer_site_completo or sitemap_completo:
                    produtos = self._deduplicar((produtos or []) + (produtos_adaptativos or []))
                else:
                    produtos = produtos_adaptativos
            except Exception as exc:
                self._log(f"[ERRO IA ABSURDA PRO] {exc}")

        produtos = self._padronizar(produtos)
        self._log(f"[SITE_AGENT] total final padronizado: {len(produtos)} produto(s)")
        return produtos

    def _executar_varredura_adaptativa(
        self,
        *,
        url: str,
        auth_context: Optional[Dict[str, Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        kwargs = kwargs or {}

        varrer_site_completo = self._bool_compat(
            kwargs.get("varrer_site_completo", kwargs.get("varredura_completa", kwargs.get("site_completo"))),
            default=False,
        )
        sitemap_completo = self._bool_compat(
            kwargs.get("sitemap_completo", kwargs.get("varrer_sitemap_completo")),
            default=varrer_site_completo,
        )

        max_workers_base = self._int_compat(kwargs.get("max_workers"), 8)
        max_workers = max(4, min(max_workers_base, 16))

        if varrer_site_completo or sitemap_completo:
            self._log("[IA] modo completo ativado: sem limite de produtos e com sitemap recursivo")
            return self._buscar_com_fallback_interno(
                url=url,
                auth_context=auth_context,
                limite=0,
                limite_paginas=0,
                max_workers=max_workers,
                usar_sitemap=True,
                usar_home=True,
                usar_categoria=True,
                modo="completo",
                sitemap_completo=sitemap_completo,
                varrer_site_completo=varrer_site_completo,
            )

        limite_base = self._int_compat(kwargs.get("limite", kwargs.get("limite_links", 300)), 300)
        paginas_base = self._int_compat(kwargs.get("limite_paginas"), 20)

        tentativas = [
            {
                "modo": "padrao",
                "limite": max(limite_base, 120),
                "limite_paginas": max(paginas_base, 12),
                "max_workers": max(4, min(max_workers, 8)),
                "usar_sitemap": True,
                "usar_home": True,
                "usar_categoria": True,
            },
            {
                "modo": "profundo",
                "limite": max(int(limite_base * 2), limite_base + 200),
                "limite_paginas": max(paginas_base + 20, 40),
                "max_workers": max(6, min(max_workers + 2, 12)),
                "usar_sitemap": True,
                "usar_home": True,
                "usar_categoria": True,
            },
            {
                "modo": "agressivo",
                "limite": max(int(limite_base * 4), limite_base + 500),
                "limite_paginas": max(paginas_base + 60, 80),
                "max_workers": max(8, min(max_workers + 4, 16)),
                "usar_sitemap": True,
                "usar_home": True,
                "usar_categoria": True,
            },
        ]

        melhor_resultado: List[Dict[str, Any]] = []

        for tentativa in tentativas:
            self._log(
                f"[IA] tentativa modo={tentativa['modo']} "
                f"limite={tentativa['limite']} "
                f"paginas={tentativa['limite_paginas']} "
                f"workers={tentativa['max_workers']}"
            )

            produtos = self._buscar_com_fallback_interno(
                url=url,
                auth_context=auth_context,
                limite=tentativa["limite"],
                limite_paginas=tentativa["limite_paginas"],
                max_workers=tentativa["max_workers"],
                usar_sitemap=tentativa["usar_sitemap"],
                usar_home=tentativa["usar_home"],
                usar_categoria=tentativa["usar_categoria"],
                modo=tentativa["modo"],
                sitemap_completo=False,
                varrer_site_completo=False,
            )

            if len(produtos) > len(melhor_resultado):
                melhor_resultado = produtos

            if produtos:
                bons = [p for p in produtos if self._score_produto(p) >= 5]
                self._log(
                    f"[IA] tentativa {tentativa['modo']} encontrou "
                    f"{len(produtos)} produto(s), {len(bons)} com score bom"
                )

                # BLINGFIX: não parar com 12 produtos.
                # Só consolida quando achou um volume razoável ou terminou as tentativas.
                if len(bons) >= 80 or len(produtos) >= 150:
                    self._log(f"[IA] sucesso consolidado na tentativa {tentativa['modo']}")
                    return produtos

        return melhor_resultado

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

    def _fornecedor_eh_generico(self, fornecedor: Any) -> bool:
        if fornecedor is None:
            return False
        try:
            nome = str(getattr(fornecedor, "nome", "") or "").strip().lower()
            classe = fornecedor.__class__.__name__.strip().lower()
            return "genérico" in nome or "generico" in nome or "generic" in classe
        except Exception:
            return False

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
    # HTTP / SSL BLINDADO
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
        session.verify = True

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

            if auth_context.get("ssl_inseguro") is True:
                session.verify = False

        return session

    def _candidate_urls(self, url: str) -> List[str]:
        base = self._normalizar_url(url)
        if not base:
            return []

        parsed = urlparse(base)
        host = (parsed.netloc or "").strip()
        path = parsed.path or "/"
        query = f"?{parsed.query}" if parsed.query else ""
        variants: List[str] = []

        def add(u: str) -> None:
            u = self._texto_limpo(u)
            if u and u not in variants:
                variants.append(u)

        add(base)

        if host.startswith("www."):
            host_sem_www = host[4:]
            add(f"{parsed.scheme}://{host_sem_www}{path}{query}")
            if parsed.scheme == "https":
                add(f"http://{host_sem_www}{path}{query}")
                add(f"http://{host}{path}{query}")
        else:
            add(f"{parsed.scheme}://www.{host}{path}{query}")
            if parsed.scheme == "https":
                add(f"http://{host}{path}{query}")
                add(f"http://www.{host}{path}{query}")

        return variants

    def _request_with_ssl_fallback(
        self,
        session: requests.Session,
        url: str,
        *,
        timeout: int = 30,
        allow_redirects: bool = True,
    ) -> Tuple[Optional[requests.Response], str]:
        candidates = self._candidate_urls(url)
        last_error: Optional[Exception] = None
        final_url = self._normalizar_url(url)

        for candidate in candidates:
            try:
                resp = session.get(
                    candidate,
                    timeout=timeout,
                    allow_redirects=allow_redirects,
                    verify=True,
                )
                final_url = str(resp.url)
                return resp, final_url
            except SSLError as exc:
                last_error = exc
                self._log(f"[SSL WARN] {candidate} -> {exc}")

                try:
                    resp = session.get(
                        candidate,
                        timeout=timeout,
                        allow_redirects=allow_redirects,
                        verify=False,
                    )
                    final_url = str(resp.url)
                    self._log(f"[SSL BYPASS OK] {candidate} -> {final_url}")
                    return resp, final_url
                except Exception as exc_insecure:
                    last_error = exc_insecure
                    self._log(f"[SSL BYPASS FALHOU] {candidate} -> {exc_insecure}")
                    continue
            except RequestException as exc:
                last_error = exc
                self._log(f"[HTTP WARN] {candidate} -> {exc}")
                continue
            except Exception as exc:
                last_error = exc
                self._log(f"[HTTP ERRO] {candidate} -> {exc}")
                continue

        if last_error:
            raise last_error

        return None, final_url

    # ------------------------------------------------------------------
    # FALLBACK INTERNO / HTTP-FIRST
    # ------------------------------------------------------------------
    def _buscar_com_fallback_interno(
        self,
        *,
        url: str,
        auth_context: Optional[Dict[str, Any]] = None,
        limite: int = 120,
        limite_paginas: int = 8,
        max_workers: int = 8,
        usar_sitemap: bool = True,
        usar_home: bool = True,
        usar_categoria: bool = True,
        modo: str = "padrao",
        sitemap_completo: bool = False,
        varrer_site_completo: bool = False,
    ) -> List[Dict[str, Any]]:
        session = self._build_session(auth_context=auth_context)
        self._log(f"[CRAWLER] iniciando varredura em: {url} | modo={modo}")

        sem_limite = limite in (None, 0, -1) or sitemap_completo or varrer_site_completo
        limite_links = 999999 if sem_limite else max(int(limite), 1)
        limite_pag = 999999 if sem_limite else max(int(limite_paginas or 1), 1)

        paginas_alvo: List[str] = []
        links_produtos: List[str] = []
        produtos_coletados: List[Dict[str, Any]] = []

        vistos_paginas: Set[str] = set()
        vistos_links_produto: Set[str] = set()

        url = self._normalizar_url(url)
        host_base = self._hostname(url)

        products_url = self._texto_limpo((auth_context or {}).get("products_url"))
        if products_url:
            products_url = self._normalizar_url(products_url)
            if products_url:
                paginas_alvo.append(products_url)

        if usar_home and url:
            paginas_alvo.append(url)

        if usar_sitemap and url:
            links_sitemap = self._descobrir_links_via_sitemap(
                session,
                url,
                limite=0 if sem_limite else limite_links * 2,
                recursivo=True,
            )
            self._log(f"[SITEMAP] total de links descobertos: {len(links_sitemap)}")

            for link_sitemap in links_sitemap:
                if self._hostname(link_sitemap) != host_base and host_base:
                    continue

                if self._url_parece_produto(link_sitemap):
                    if link_sitemap not in vistos_links_produto:
                        vistos_links_produto.add(link_sitemap)
                        links_produtos.append(link_sitemap)
                elif usar_categoria and self._url_parece_categoria(link_sitemap):
                    paginas_alvo.append(link_sitemap)
                elif varrer_site_completo:
                    paginas_alvo.append(link_sitemap)

                if not sem_limite and len(links_produtos) >= limite_links:
                    break

        paginas_alvo = self._deduplicar_lista_urls(paginas_alvo)

        fila_paginas = list(paginas_alvo)
        idx = 0

        while idx < len(fila_paginas) and len(vistos_paginas) < limite_pag:
            pagina = fila_paginas[idx]
            idx += 1

            if not pagina or pagina in vistos_paginas:
                continue
            if host_base and self._hostname(pagina) != host_base:
                continue

            vistos_paginas.add(pagina)

            html, final_url = self._get_html(session, pagina)
            if not html:
                continue

            if len(vistos_paginas) == 1 or len(vistos_paginas) % 10 == 0:
                self._log(
                    f"[CRAWLER] páginas analisadas={len(vistos_paginas)} "
                    f"| links_produto={len(links_produtos)} | atual={final_url}"
                )

            jsonld_produtos = self._extrair_produtos_jsonld(html, final_url)
            if jsonld_produtos:
                produtos_coletados.extend(jsonld_produtos)

            if self._pagina_parece_produto(html, final_url) and not self._pagina_parece_categoria(html, final_url):
                produto = self._extrair_produto_da_pagina(html, final_url)
                if produto:
                    produtos_coletados.append(produto)

            novos_links = self._extrair_links_produto(html, final_url, limite=0 if sem_limite else limite_links)
            for link in novos_links:
                if link not in vistos_links_produto:
                    vistos_links_produto.add(link)
                    links_produtos.append(link)

            if usar_categoria:
                links_categoria = self._extrair_links_categoria(html, final_url, limite=0 if sem_limite else limite_pag)
                for link_cat in links_categoria:
                    if link_cat not in vistos_paginas and link_cat not in fila_paginas:
                        fila_paginas.append(link_cat)

            for link_pag in self._extrair_links_paginacao(
                html,
                final_url,
                limite_paginas=0 if sem_limite else limite_pag,
            ):
                if link_pag not in vistos_paginas and link_pag not in fila_paginas:
                    fila_paginas.append(link_pag)

            if varrer_site_completo:
                for link_interno in self._extrair_links_internos(html, final_url, limite=0):
                    if link_interno in vistos_paginas or link_interno in fila_paginas:
                        continue
                    if self._url_parece_produto(link_interno):
                        if link_interno not in vistos_links_produto:
                            vistos_links_produto.add(link_interno)
                            links_produtos.append(link_interno)
                    elif self._url_parece_categoria(link_interno):
                        fila_paginas.append(link_interno)

            if not sem_limite and len(links_produtos) >= limite_links:
                break

        self._log(f"[CRAWLER] coletados {len(links_produtos)} links de produto")

        links_para_coletar = self._deduplicar_lista_urls(links_produtos)
        if not sem_limite:
            links_para_coletar = links_para_coletar[:limite_links]

        produtos_detalhados = self._coletar_paginas_produto_concorrente(
            session=session,
            links_produtos=links_para_coletar,
            max_workers=max_workers,
        )

        produtos_coletados.extend(produtos_detalhados)
        produtos_coletados = self._classificar_e_filtrar_produtos(produtos_coletados)
        produtos_coletados = self._padronizar(produtos_coletados)
        return produtos_coletados

    def _coletar_paginas_produto_concorrente(
        self,
        *,
        session: requests.Session,
        links_produtos: List[str],
        max_workers: int = 8,
    ) -> List[Dict[str, Any]]:
        resultados: List[Dict[str, Any]] = []
        if not links_produtos:
            return resultados

        max_workers = max(1, min(int(max_workers or 1), 16))

        def _worker(link_produto: str) -> Optional[Dict[str, Any]]:
            html_prod, final_prod = self._get_html(session, link_produto)
            if not html_prod:
                return None
            return self._extrair_produto_da_pagina(html_prod, final_prod)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futuros = {executor.submit(_worker, link): link for link in links_produtos}
            total = len(futuros)
            concluidos = 0

            for futuro in as_completed(futuros):
                concluidos += 1
                try:
                    produto = futuro.result()
                    if produto:
                        resultados.append(produto)
                except Exception as exc:
                    link = futuros.get(futuro, "")
                    self._log(f"[WORKER ERRO] {link} -> {exc}")

                if concluidos == 1 or concluidos % 25 == 0 or concluidos == total:
                    self._log(
                        f"[CRAWLER] páginas de produto processadas={concluidos}/{total} "
                        f"| produtos válidos={len(resultados)}"
                    )

        return resultados

    def _descobrir_links_via_sitemap(
        self,
        session: requests.Session,
        base_url: str,
        limite: int = 300,
        recursivo: bool = True,
    ) -> List[str]:
        candidatos = self._gerar_urls_sitemap(base_url)
        encontrados: List[str] = []
        vistos_links: Set[str] = set()
        vistos_sitemaps: Set[str] = set()
        fila = list(candidatos)
        sem_limite = limite in (None, 0, -1)

        while fila:
            sitemap_url = self._normalizar_url(fila.pop(0))
            if not sitemap_url or sitemap_url in vistos_sitemaps:
                continue

            vistos_sitemaps.add(sitemap_url)
            xml_texto, final_url = self._get_text(session, sitemap_url)
            if not xml_texto:
                continue

            links = self._parse_sitemap_links(xml_texto, final_url)
            if not links:
                continue

            self._log(f"[SITEMAP] {final_url} -> {len(links)} link(s)")

            for link in links:
                link = self._limpar_url(link)
                if not link:
                    continue

                if recursivo and self._parece_arquivo_sitemap(link):
                    if link not in vistos_sitemaps and link not in fila:
                        fila.append(link)
                    continue

                if link in vistos_links:
                    continue

                vistos_links.add(link)
                encontrados.append(link)

                if not sem_limite and len(encontrados) >= int(limite):
                    return encontrados

        return encontrados

    def _gerar_urls_sitemap(self, base_url: str) -> List[str]:
        base_url = self._normalizar_url(base_url)
        if not base_url:
            return []

        parsed = urlparse(base_url)
        raiz = f"{parsed.scheme}://{parsed.netloc}"

        candidatos = [
            f"{raiz}/sitemap.xml",
            f"{raiz}/sitemap_index.xml",
            f"{raiz}/sitemap-index.xml",
            f"{raiz}/sitemap-products.xml",
            f"{raiz}/sitemap_product.xml",
            f"{raiz}/sitemap-products-1.xml",
            f"{raiz}/product-sitemap.xml",
            f"{raiz}/products-sitemap.xml",
            f"{raiz}/produto-sitemap.xml",
            f"{raiz}/produtos-sitemap.xml",
            f"{raiz}/sitemap_produtos.xml",
            f"{raiz}/sitemap_produto.xml",
            f"{raiz}/robots.txt",
        ]
        return self._deduplicar_lista_urls(candidatos)

    def _parse_sitemap_links(self, texto: str, base_url: str) -> List[str]:
        texto = self._texto_limpo(texto)
        if not texto:
            return []

        if "sitemap:" in texto.lower() and "<urlset" not in texto.lower() and "<sitemapindex" not in texto.lower():
            links = []
            for linha in texto.splitlines():
                linha_l = linha.strip()
                if linha_l.lower().startswith("sitemap:"):
                    link = self._texto_limpo(linha_l.split(":", 1)[1])
                    if link:
                        links.append(link)
            return links

        try:
            root = ET.fromstring(texto)
        except Exception:
            links_re = re.findall(r"https?://[^\s<>'\"]+", texto)
            return [self._limpar_url(x) for x in links_re if self._limpar_url(x)]

        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}", 1)[0] + "}"

        links: List[str] = []
        for node in root.findall(f".//{ns}loc"):
            valor = self._texto_limpo(node.text)
            if valor:
                links.append(valor)

        return links

    def _parece_arquivo_sitemap(self, url: str) -> bool:
        url_l = (url or "").lower()
        return "sitemap" in url_l and (
            url_l.endswith(".xml")
            or ".xml?" in url_l
            or url_l.endswith(".gz")
            or ".gz?" in url_l
        )

    def _get_html(self, session: requests.Session, url: str) -> Tuple[str, str]:
        try:
            resp, final_url = self._request_with_ssl_fallback(
                session,
                url,
                timeout=30,
                allow_redirects=True,
            )
            if resp is None or not resp.ok:
                return "", self._normalizar_url(final_url or url)

            content_type = self._texto_limpo(resp.headers.get("Content-Type")).lower()
            texto = resp.text or ""
            if "text/html" not in content_type and "<html" not in texto.lower():
                return "", str(resp.url)

            return texto, str(resp.url)
        except Exception as exc:
            self._log(f"[GET_HTML ERRO] {url} -> {exc}")
            return "", self._normalizar_url(url)

    def _get_text(self, session: requests.Session, url: str) -> Tuple[str, str]:
        try:
            resp, final_url = self._request_with_ssl_fallback(
                session,
                url,
                timeout=30,
                allow_redirects=True,
            )
            if resp is None or not resp.ok:
                return "", self._normalizar_url(final_url or url)
            return resp.text or "", str(resp.url)
        except Exception as exc:
            self._log(f"[GET_TEXT ERRO] {url} -> {exc}")
            return "", self._normalizar_url(url)

    # ------------------------------------------------------------------
    # EXTRAÇÃO JSON-LD
    # ------------------------------------------------------------------
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
                tipo = obj.get("@type")
                tipo_lista = tipo if isinstance(tipo, list) else [tipo]
                tipo_lista = [str(t).lower() for t in tipo_lista]
                if "product" in tipo_lista:
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
        estoque: Any = ""
        disponibilidade = ""

        if isinstance(offers, list) and offers:
            offers = offers[0]

        if isinstance(offers, dict):
            preco = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice") or ""
            disponibilidade = self._texto_limpo(offers.get("availability"))
            disponibilidade_l = disponibilidade.lower()
            if "outofstock" in disponibilidade_l:
                estoque = 0
            elif "instock" in disponibilidade_l:
                estoque = 1

        imagens = item.get("image", [])
        if isinstance(imagens, str):
            imagens = [imagens]
        elif isinstance(imagens, dict):
            imagens = [imagens.get("url", "")]
        elif not isinstance(imagens, list):
            imagens = []

        imagens = [self._limpar_url(urljoin(base_url, self._texto_limpo(img.get("url") if isinstance(img, dict) else img))) for img in imagens]
        imagens = [img for img in imagens if img]

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
        nome = self._limpar_nome_produto(item.get("name"))
        descricao = self._texto_limpo(item.get("description"))

        if not nome and not url_produto:
            return None

        marca = self._normalizar_marca(marca, nome=nome, descricao=descricao)

        return {
            "url_produto": url_produto,
            "nome": nome,
            "sku": sku,
            "marca": marca,
            "categoria": self._texto_limpo(item.get("category")),
            "estoque": estoque,
            "preco": preco,
            "gtin": gtin,
            "descricao": descricao,
            "imagens": imagens,
            "_fonte": "jsonld",
        }

    # ------------------------------------------------------------------
    # HEURÍSTICAS DE PÁGINA
    # ------------------------------------------------------------------
    def _pagina_parece_produto(self, html: str, url: str) -> bool:
        page = (html or "").lower()
        url_l = (url or "").lower()
        sinais = 0

        if any(token in url_l for token in ["/produto", "/product", "/item/", "/p/"]):
            sinais += 2
        if re.search(r"/[a-z0-9\-]+-\d{3,}", url_l):
            sinais += 2
        if any(token in page for token in ['"@type":"product"', '"@type": "product"', "'@type':'product'"]):
            sinais += 3
        if any(token in page for token in ["sku", "ean", "gtin", "código", "codigo do produto"]):
            sinais += 1
        if any(token in page for token in ["comprar", "adicionar ao carrinho", "buy now", "add to cart"]):
            sinais += 1
        if re.search(r"r\$\s*\d", page):
            sinais += 1

        return sinais >= 3

    def _pagina_parece_categoria(self, html: str, url: str) -> bool:
        page = (html or "").lower()
        url_l = (url or "").lower()
        sinais = 0

        if any(token in url_l for token in ["/categoria", "/categorias", "/catalog", "/catalogo", "/colecao", "/collection"]):
            sinais += 2
        if "filtros" in page or "ordenar por" in page or "mostrar " in page:
            sinais += 1
        if page.count("product-item") >= 3 or page.count("produto") >= 10:
            sinais += 1
        if "breadcrumb" in page and any(token in page for token in ["categoria", "departamento", "coleção"]):
            sinais += 1

        return sinais >= 2

    def _url_parece_produto(self, url: str) -> bool:
        url_l = (url or "").lower()

        if self._url_indesejada(url_l):
            return False

        if any(token in url_l for token in ["/produto/", "/produtos/", "/product/", "/item/", "/p/"]):
            return True

        if re.search(r"/[a-z0-9\-]+-\d{3,}", url_l):
            return True

        if any(token in url_l for token in ["sku=", "produto=", "product_id=", "idproduto=", "id_produto=", "item_id="]):
            return True

        if any(token in url_l for token in ["iphone-", "smartphone-", "tablet-", "smartwatch-", "fone-", "caixa-de-som-"]):
            return True

        return False

    def _url_parece_categoria(self, url: str) -> bool:
        url_l = (url or "").lower()
        if self._url_indesejada(url_l):
            return False

        return any(token in url_l for token in self.CATEGORY_HINTS)

    def _url_indesejada(self, url: str) -> bool:
        url_l = (url or "").lower()
        return any(token in url_l for token in self.BAD_LINK_HINTS)

    # ------------------------------------------------------------------
    # EXTRAÇÃO DE LINKS
    # ------------------------------------------------------------------
    def _extrair_links_produto(self, html: str, base_url: str, limite: int = 120) -> List[str]:
        soup = BeautifulSoup(html or "", "html.parser")
        base_host = self._hostname(base_url)
        links: List[str] = []
        vistos: Set[str] = set()
        sem_limite = limite in (None, 0, -1)

        candidatos_css = [
            "a[href]",
            "[class*='product'] a[href]",
            "[class*='produto'] a[href]",
            "[data-product-link]",
        ]

        for selector in candidatos_css:
            try:
                elementos = soup.select(selector)
            except Exception:
                elementos = []

            for el in elementos:
                href = self._texto_limpo(el.get("href") or el.get("data-product-link"))
                if not href:
                    continue

                url = self._limpar_url(urljoin(base_url, href))
                if not url:
                    continue
                if self._hostname(url) != base_host:
                    continue
                if not self._url_parece_produto(url):
                    continue
                if self._url_parece_categoria(url):
                    continue
                if url in vistos:
                    continue

                vistos.add(url)
                links.append(url)

                if not sem_limite and len(links) >= int(limite):
                    return links

        return links

    def _extrair_links_categoria(self, html: str, base_url: str, limite: int = 40) -> List[str]:
        soup = BeautifulSoup(html or "", "html.parser")
        base_host = self._hostname(base_url)
        links: List[str] = []
        vistos: Set[str] = set()
        sem_limite = limite in (None, 0, -1)

        for a in soup.find_all("a", href=True):
            href = self._texto_limpo(a.get("href"))
            if not href:
                continue

            url = self._limpar_url(urljoin(base_url, href))
            if not url:
                continue
            if self._hostname(url) != base_host:
                continue
            if not self._url_parece_categoria(url):
                continue
            if self._url_parece_produto(url):
                continue
            if url in vistos:
                continue

            vistos.add(url)
            links.append(url)

            if not sem_limite and len(links) >= int(limite):
                break

        return links

    def _extrair_links_paginacao(self, html: str, base_url: str, limite_paginas: int = 8) -> List[str]:
        soup = BeautifulSoup(html or "", "html.parser")
        base_host = self._hostname(base_url)
        links: List[str] = []
        vistos: Set[str] = set()
        sem_limite = limite_paginas in (None, 0, -1)

        for a in soup.find_all("a", href=True):
            href = self._texto_limpo(a.get("href"))
            texto = self._texto_limpo(a.get_text(" ", strip=True)).lower()
            if not href:
                continue

            url = self._limpar_url(urljoin(base_url, href))
            if not url:
                continue
            if self._hostname(url) != base_host:
                continue

            url_l = url.lower()
            parece_paginacao = (
                any(token in url_l for token in ["page=", "/page/", "pagina=", "p=", "?pg=", "&pg=", "?page=", "&page="])
                or texto in {"próxima", "proxima", "next", ">", ">>", "avançar", "avancar"}
                or "próxima" in texto
                or "proxima" in texto
                or "next" in texto
            )

            if not parece_paginacao:
                continue
            if url in vistos:
                continue

            vistos.add(url)
            links.append(url)

            if not sem_limite and len(links) >= int(limite_paginas):
                break

        return links

    def _extrair_links_internos(self, html: str, base_url: str, limite: int = 0) -> List[str]:
        soup = BeautifulSoup(html or "", "html.parser")
        base_host = self._hostname(base_url)
        links: List[str] = []
        vistos: Set[str] = set()
        sem_limite = limite in (None, 0, -1)

        for a in soup.find_all("a", href=True):
            href = self._texto_limpo(a.get("href"))
            if not href:
                continue

            url = self._limpar_url(urljoin(base_url, href))
            if not url:
                continue
            if self._hostname(url) != base_host:
                continue
            if self._url_indesejada(url):
                continue
            if url in vistos:
                continue

            vistos.add(url)
            links.append(url)

            if not sem_limite and len(links) >= int(limite):
                break

        return links

    # ------------------------------------------------------------------
    # EXTRAÇÃO DE PRODUTO
    # ------------------------------------------------------------------
    def _extrair_produto_da_pagina(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        jsonld = self._extrair_produtos_jsonld(html, url)
        if jsonld:
            melhores = sorted(jsonld, key=self._score_produto, reverse=True)
            melhor = melhores[0]
            if self._score_produto(melhor) >= 4:
                return melhor

        soup = BeautifulSoup(html or "", "html.parser")
        texto_pagina = soup.get_text(" ", strip=True)

        nome = self._extrair_nome_produto(soup)
        preco = self._extrair_preco(texto_pagina, soup)
        sku = self._extrair_sku(texto_pagina, soup)
        gtin = self._extrair_gtin(texto_pagina, soup)
        marca = self._extrair_marca(soup, texto_pagina, nome)
        categoria = self._extrair_categoria(soup, url=url)
        descricao = self._extrair_descricao(soup)
        imagens = self._extrair_imagens(soup, url)
        estoque = self._extrair_estoque(texto_pagina, soup)

        produto = {
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
            "_fonte": "heuristica",
        }

        if self._score_produto(produto) < 3:
            return None

        return produto

    def _extrair_nome_produto(self, soup: BeautifulSoup) -> str:
        candidatos = [
            {"name": "meta", "attrs": {"property": "og:title"}},
            {"name": "meta", "attrs": {"name": "twitter:title"}},
            {"name": "h1", "attrs": {}},
            {"name": True, "attrs": {"itemprop": "name"}},
            {"name": True, "attrs": {"class": re.compile(r"(product.*title|produto.*titulo|title|nome-produto)", re.I)}},
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
                valor = self._limpar_nome_produto(unescape(valor))
                if valor and len(valor) >= 3:
                    return valor[:220]
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

        for seletor in [
            "[itemprop='price']",
            "[class*='price']",
            "[class*='preco']",
            "[data-price]",
        ]:
            try:
                el = soup.select_one(seletor)
            except Exception:
                el = None
            if not el:
                continue
            valor = self._texto_limpo(
                el.get("content")
                or el.get("data-price")
                or el.get_text(" ", strip=True)
            )
            if re.search(r"\d", valor):
                return valor

        match = re.search(r"r\$\s*([\d\.\,]+)", texto_pagina.lower())
        if match:
            return match.group(1)

        return ""

    def _extrair_sku(self, texto_pagina: str, soup: BeautifulSoup) -> str:
        for tag in soup.find_all(attrs={"itemprop": re.compile(r"sku", re.I)}):
            valor = self._texto_limpo(tag.get("content") or tag.get_text(" ", strip=True))
            if valor:
                return valor[:80]

        padroes = [
            r"(?:sku|código|codigo)\s*[:#]?\s*([a-zA-Z0-9\-_./]+)",
            r"(?:ref\.?|referência|referencia)\s*[:#]?\s*([a-zA-Z0-9\-_./]+)",
        ]
        for padrao in padroes:
            match = re.search(padrao, texto_pagina, flags=re.I)
            if match:
                return self._texto_limpo(match.group(1))[:80]

        return ""

    def _extrair_gtin(self, texto_pagina: str, soup: BeautifulSoup) -> str:
        for chave in ["gtin13", "gtin12", "gtin14", "gtin8", "gtin"]:
            try:
                tag = soup.find(attrs={"itemprop": re.compile(chave, re.I)})
                if tag:
                    valor = self._texto_limpo(tag.get("content") or tag.get_text(" ", strip=True))
                    numeros = re.sub(r"\D", "", valor)
                    if len(numeros) in (8, 12, 13, 14):
                        return numeros
            except Exception:
                continue

        match = re.search(r"(?:ean|gtin|código de barras|codigo de barras)\s*[:#]?\s*(\d{8,14})", texto_pagina, flags=re.I)
        if match:
            return match.group(1)

        return ""

    def _extrair_marca(self, soup: BeautifulSoup, texto_pagina: str, nome: str) -> str:
        for tag in soup.find_all(attrs={"itemprop": re.compile(r"brand", re.I)}):
            valor = self._normalizar_marca(
                tag.get("content") or tag.get_text(" ", strip=True),
                nome=nome,
                descricao=texto_pagina,
            )
            if valor:
                return valor[:80]

        padroes = [
            r"(?:marca)\s*[:#]?\s*([A-Za-z0-9À-ÿ\-_ ]{2,60})",
            r"(?:fabricante)\s*[:#]?\s*([A-Za-z0-9À-ÿ\-_ ]{2,60})",
        ]
        for padrao in padroes:
            match = re.search(padrao, texto_pagina, flags=re.I)
            if match:
                marca = self._normalizar_marca(match.group(1), nome=nome, descricao=texto_pagina)
                if marca:
                    return marca[:80]

        return self._normalizar_marca("", nome=nome, descricao=texto_pagina)[:80]

    def _extrair_categoria(self, soup: BeautifulSoup, url: str = "") -> str:
        breadcrumbs = []
        try:
            for tag in soup.find_all(attrs={"class": re.compile(r"breadcrumb", re.I)}):
                texto = self._texto_limpo(tag.get_text(" > ", strip=True))
                if texto:
                    breadcrumbs.append(texto)
            if breadcrumbs:
                return breadcrumbs[0][:220]
        except Exception:
            pass

        if url:
            partes = [p for p in urlparse(url).path.split("/") if self._texto_limpo(p)]
            for parte in partes[:-1]:
                parte_l = parte.lower()
                if parte_l not in {"produto", "produtos", "product", "products", "item", "p"}:
                    if len(parte_l) > 2:
                        return self._texto_limpo(parte.replace("-", " ").title())[:120]

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
                if url and url not in vistos and self._imagem_valida(url):
                    vistos.add(url)
                    imagens.append(url)

        for img in soup.find_all("img"):
            src = self._texto_limpo(
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
                or img.get("data-lazy")
                or img.get("data-zoom-image")
            )
            if not src:
                continue
            url = self._limpar_url(urljoin(base_url, src))
            if not url:
                continue
            if not self._imagem_valida(url):
                continue
            if url in vistos:
                continue
            vistos.add(url)
            imagens.append(url)
            if len(imagens) >= 12:
                break

        return imagens

    def _imagem_valida(self, url: str) -> bool:
        url_l = (url or "").lower()
        if not url_l:
            return False
        if any(token in url_l for token in ["logo", "icon", "sprite", "banner", "placeholder", "whatsapp", "facebook", "instagram"]):
            return False
        return True

    def _extrair_estoque(self, texto_pagina: str, soup: BeautifulSoup) -> Any:
        texto = self._texto_limpo(texto_pagina).lower()

        if any(
            termo in texto
            for termo in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado", "out of stock"]
        ):
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

    # ------------------------------------------------------------------
    # QUALIDADE / FILTRO
    # ------------------------------------------------------------------
    def _score_produto(self, produto: Dict[str, Any]) -> int:
        score = 0
        nome = self._texto_limpo(produto.get("nome"))
        preco = produto.get("preco")
        url_produto = self._texto_limpo(produto.get("url_produto"))
        sku = self._texto_limpo(produto.get("sku"))
        gtin = self._texto_limpo(produto.get("gtin"))
        descricao = self._texto_limpo(produto.get("descricao"))
        imagens = produto.get("imagens")
        categoria = self._texto_limpo(produto.get("categoria"))
        estoque = produto.get("estoque")

        if nome and len(nome) >= 4:
            score += 2
        if url_produto and self._url_parece_produto(url_produto):
            score += 2
        if sku:
            score += 1
        if gtin:
            score += 1
        if descricao and len(descricao) >= 20:
            score += 1
        if categoria:
            score += 1
        if imagens:
            if isinstance(imagens, list) and len(imagens) > 0:
                score += 1
            elif isinstance(imagens, str) and self._texto_limpo(imagens):
                score += 1
        try:
            preco_n = self._normalizar_preco(preco)
            if preco_n > 0:
                score += 2
        except Exception:
            pass
        try:
            est_n = self._normalizar_estoque(estoque)
            if est_n >= 0:
                score += 1
        except Exception:
            pass

        return score

    def _classificar_e_filtrar_produtos(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidatos: List[Dict[str, Any]] = []
        for produto in produtos:
            if not isinstance(produto, dict):
                continue
            if self._score_produto(produto) < 3:
                continue
            candidatos.append(produto)

        candidatos.sort(key=self._score_produto, reverse=True)
        return self._deduplicar(candidatos)

    # ------------------------------------------------------------------
    # UTILS
    # ------------------------------------------------------------------
    def _limpar_url(self, url: str) -> str:
        url = self._normalizar_url(url)
        if not url:
            return ""
        return url.split("#")[0].strip()

    def _hostname(self, url: str) -> str:
        try:
            host = (urlparse(self._normalizar_url(url)).hostname or "").strip().lower()
            if host.startswith("www."):
                host = host[4:]
            return host
        except Exception:
            return ""

    def _deduplicar_lista_urls(self, urls: Iterable[str]) -> List[str]:
        vistos: Set[str] = set()
        resultado: List[str] = []
        for url in urls:
            url_l = self._limpar_url(url)
            if not url_l or url_l in vistos:
                continue
            vistos.add(url_l)
            resultado.append(url_l)
        return resultado

    def _bool_compat(self, valor: Any, default: bool = False) -> bool:
        if valor is None:
            return default
        if isinstance(valor, bool):
            return valor
        texto = self._texto_limpo(valor).lower()
        if not texto:
            return default
        if texto in {"1", "true", "sim", "yes", "on", "s"}:
            return True
        if texto in {"0", "false", "nao", "não", "no", "off", "n"}:
            return False
        return default

    def _int_compat(self, valor: Any, default: int) -> int:
        try:
            if valor is None or valor == "":
                return int(default)
            return int(valor)
        except Exception:
            return int(default)

    # ------------------------------------------------------------------
    # PADRONIZAÇÃO
    # ------------------------------------------------------------------
    def _padronizar(self, produtos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        resultado: List[Dict[str, Any]] = []

        for p in produtos:
            if not isinstance(p, dict):
                continue

            nome = self._limpar_nome_produto(p.get("nome"))
            url_produto = self._texto_limpo(p.get("url_produto"))
            sku = self._texto_limpo(p.get("sku"))
            descricao = self._texto_limpo(p.get("descricao"))
            marca = self._normalizar_marca(p.get("marca"), nome=nome, descricao=descricao)
            categoria = self._texto_limpo(p.get("categoria"))
            gtin = self._normalizar_gtin(p.get("gtin"))

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

    def _normalizar_gtin(self, valor: Any) -> str:
        numeros = re.sub(r"\D", "", self._texto_limpo(valor))
        if len(numeros) in (8, 12, 13, 14):
            return numeros
        return ""

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

        return "|".join(lista_final[:12])

    def _texto_limpo(self, valor: Any) -> str:
        texto = str(valor or "").strip()
        if texto.lower() in {"nan", "none", "null"}:
            return ""
        texto = unescape(texto)
        texto = texto.replace("\ufeff", "").replace("\x00", "")
        texto = re.sub(r"[\r\n\t]+", " ", texto)
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto

    def _normalizar_url(self, url: str) -> str:
        texto = self._texto_limpo(url)
        if not texto:
            return ""
        if texto.startswith("//"):
            texto = f"https:{texto}"
        if not texto.startswith(("http://", "https://")):
            texto = f"https://{texto}"
        return texto

    def _limpar_nome_produto(self, valor: Any) -> str:
        texto = self._texto_limpo(valor)
        texto = re.sub(r"\s*[-|]\s*Mega Center.*$", "", texto, flags=re.I)
        texto = re.sub(r"\s*[-|]\s*Comprar.*$", "", texto, flags=re.I)
        return texto.strip()

    def _normalizar_marca(self, marca: Any, *, nome: str = "", descricao: str = "") -> str:
        marca_txt = self._texto_limpo(marca)
        marca_txt = re.sub(r"\s+", " ", marca_txt).strip(" -|:/")

        if self._marca_invalida(marca_txt):
            marca_txt = ""

        if not marca_txt:
            marca_txt = self._inferir_marca(nome=nome, descricao=descricao)

        if self._marca_invalida(marca_txt):
            return ""

        return marca_txt[:80]

    def _marca_invalida(self, marca: str) -> bool:
        marca_l = self._sem_acentos(self._texto_limpo(marca)).lower()
        if not marca_l:
            return True

        bloqueadas = {self._sem_acentos(x).lower() for x in self.MARCAS_LOJA_BLOQUEADAS}
        if marca_l in bloqueadas:
            return True

        if "mega center" in marca_l or "megacenter" in marca_l:
            return True

        if len(marca_l) > 80:
            return True

        return False

    def _inferir_marca(self, *, nome: str = "", descricao: str = "") -> str:
        texto = f" {nome or ''} {descricao or ''} "
        texto_norm = self._sem_acentos(texto).lower()

        for marca in self.MARCAS_CONHECIDAS:
            marca_norm = self._sem_acentos(marca).lower()
            if re.search(rf"(?<![a-z0-9]){re.escape(marca_norm)}(?![a-z0-9])", texto_norm):
                return marca

        nome_limpo = self._texto_limpo(nome)
        if nome_limpo:
            primeira = nome_limpo.split(" ")[0].strip(" -:/")
            genericas = {
                "cabo", "fone", "caixa", "carregador", "pelicula", "película",
                "capinha", "suporte", "adaptador", "controle", "mouse", "teclado",
                "chip", "troca", "tela", "smartphone", "celular", "produto",
                "kit", "mini", "novo", "nova", "original", "fonte", "capa",
            }
            if (
                primeira
                and len(primeira) >= 3
                and not primeira.isdigit()
                and primeira.lower() not in genericas
                and not self._marca_invalida(primeira)
            ):
                return primeira

        return ""

    def _sem_acentos(self, texto: str) -> str:
        mapa = str.maketrans(
            "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
            "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC",
        )
        return (texto or "").translate(mapa)

    def _filtrar_kwargs_fornecedor(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        removidos = {
            "base_url",
            "diagnostico",
            "termo",
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
            chave = chave.lower().strip()
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

        if st is not None:
            try:
                if "logs" not in st.session_state:
                    st.session_state["logs"] = []
                st.session_state["logs"].append(f"{time.strftime('%H:%M:%S')} {mensagem}")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # DATAFRAME
    # ------------------------------------------------------------------
    def para_dataframe(self, produtos: List[Dict[str, Any]]) -> pd.DataFrame:
        produtos = self._padronizar(produtos)

        colunas = [
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

        if not produtos:
            return pd.DataFrame(columns=colunas)

        df = pd.DataFrame(produtos).fillna("")

        for col in colunas:
            if col not in df.columns:
                df[col] = ""

        if "estoque" in df.columns:
            df["estoque"] = df["estoque"].apply(self._normalizar_estoque)

        if "preco" in df.columns:
            df["preco"] = df["preco"].apply(self._normalizar_preco)

        if "imagens" in df.columns:
            df["imagens"] = df["imagens"].apply(self._normalizar_imagens)

        if "gtin" in df.columns:
            df["gtin"] = df["gtin"].apply(self._normalizar_gtin)

        if "marca" in df.columns:
            df["marca"] = df.apply(
                lambda row: self._normalizar_marca(
                    row.get("marca", ""),
                    nome=row.get("nome", ""),
                    descricao=row.get("descricao", ""),
                ),
                axis=1,
            )

        return df[colunas].reset_index(drop=True)

    # ------------------------------------------------------------------
    # DIAGNÓSTICO
    # ------------------------------------------------------------------
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

        fonte = "fallback_interno_http_pro"
        nome_fornecedor_l = nome_fornecedor.lower()

        if nome_fornecedor_l.startswith("fornecedor gen"):
            fonte = "generic_supplier"
        elif "mega center" in nome_fornecedor_l:
            fonte = "fornecedor_especifico"
        elif "atacadum" in nome_fornecedor_l:
            fonte = "fornecedor_especifico"

        df_diag = pd.DataFrame(produtos).copy() if produtos else pd.DataFrame()
        if not df_diag.empty:
            df_diag["score"] = df_diag.apply(
                lambda row: self._score_produto(row.to_dict()),
                axis=1,
            )
            df_diag["valido"] = df_diag["score"] >= 3

        return {
            "url": url,
            "fornecedor": nome_fornecedor or "Fornecedor Genérico",
            "fonte_descoberta": fonte,
            "diagnostico_df": df_diag,
            "total_descobertos": int(len(produtos)),
            "total_validos": int(sum(1 for p in produtos if self._score_produto(p) >= 3)),
            "total_rejeitados": int(sum(1 for p in produtos if self._score_produto(p) < 3)),
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

    # BLINGFIX:
    # Quando o fluxo pedir varrer tudo, usar:
    # buscar_produtos_site_com_gpt(base_url=..., varrer_site_completo=True, sitemap_completo=True)
    return agent.buscar_dataframe(
        base_url=base_url,
        diagnostico=diagnostico,
        auth_context=auth_context,
        **kwargs_execucao,
    )
