def _adicionar_url_imagem(
    urls: List[str],
    url: str,
    base_url: str,
    contexto: str = "",
    min_score: int = 0,
) -> None:
    normalizada = _normalizar_url_imagem(url, base_url)
    if not normalizada:
        return

    if _score_imagem(normalizada, base_url, contexto) < min_score:
        return

    if normalizada not in urls:
        urls.append(normalizada)


def _extrair_imagens_por_selectors(soup: BeautifulSoup, base_url: str) -> List[str]:
    urls: List[str] = []

    for selector in PRODUCT_IMAGE_SELECTORS:
        try:
            elementos = soup.select(selector)
        except Exception:
            elementos = []

        for el in elementos:
            candidatos = [
                el.get("src"),
                el.get("data-src"),
                el.get("data-original"),
                el.get("data-lazy"),
                el.get("data-zoom-image"),
                el.get("data-large_image"),
                el.get("href"),
                el.get("srcset"),
            ]

            for candidato in candidatos:
                _adicionar_url_imagem(
                    urls=urls,
                    url=candidato or "",
                    base_url=base_url,
                    contexto=selector,
                    min_score=4,
                )

    return urls


def _collect_images(soup: BeautifulSoup, base_url: str) -> List[str]:
    urls: List[str] = []

    # 1) Prioriza metas de imagem do produto
    for meta_prop in ("og:image", "twitter:image"):
        meta_url = _extract_meta(soup, meta_prop)
        _adicionar_url_imagem(
            urls=urls,
            url=meta_url,
            base_url=base_url,
            contexto=meta_prop,
            min_score=2,
        )

    # 2) Prioriza galerias e seletores típicos de produto
    for url in _extrair_imagens_por_selectors(soup, base_url):
        if url not in urls:
            urls.append(url)

    # 3) Fallback: img tags gerais, mas com filtro mais rígido
    if len(urls) < 2:
        for img in soup.find_all("img"):
            candidatos = [
                img.get("src"),
                img.get("data-src"),
                img.get("data-original"),
                img.get("data-lazy"),
                img.get("data-zoom-image"),
                img.get("data-large_image"),
                img.get("srcset"),
            ]

            classes = " ".join(img.get("class", []) or [])
            alt = _clean_text(img.get("alt"))
            parent_class = ""
            try:
                parent = img.parent
                if parent:
                    parent_class = " ".join(parent.get("class", []) or [])
            except Exception:
                parent_class = ""

            contexto = " ".join([classes, alt, parent_class]).strip()

            for candidato in candidatos:
                _adicionar_url_imagem(
                    urls=urls,
                    url=candidato or "",
                    base_url=base_url,
                    contexto=contexto,
                    min_score=6,
                )

    return urls[:12]


def _extract_breadcrumb_category(soup: BeautifulSoup) -> str:
    trilhas: List[str] = []

    nav = soup.find(attrs={"aria-label": re.compile("breadcrumb", re.I)})
    if nav:
        trilhas.extend([_clean_text(x.get_text(" ", strip=True)) for x in nav.find_all(["a", "span", "li"])])

    if not trilhas:
        for seletor in [".breadcrumb a", ".breadcrumbs a", "[class*=breadcrumb] a", "[class*=breadcrumbs] a"]:
            itens = soup.select(seletor)
            if itens:
                trilhas.extend([_clean_text(x.get_text(" ", strip=True)) for x in itens])
                break

    trilhas = [x for x in trilhas if x and x.lower() not in {"home", "inicio", "início"}]

    unicos: List[str] = []
    for item in trilhas:
        if item not in unicos:
            unicos.append(item)

    return " > ".join(unicos)


def _find_candidate_text(soup: BeautifulSoup, selectors: List[str]) -> str:
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            texto = _clean_text(el.get_text(" ", strip=True))
            if texto:
                return texto
    return ""


def _extract_specs_map(soup: BeautifulSoup) -> Dict[str, str]:
    specs: Dict[str, str] = {}

    for row in soup.select("table tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2:
            chave = _clean_text(cells[0].get_text(" ", strip=True)).lower()
            valor = _clean_text(cells[1].get_text(" ", strip=True))
            if chave and valor and chave not in specs:
                specs[chave] = valor

    for item in soup.select("dl"):
        dts = item.find_all("dt")
        dds = item.find_all("dd")
        for dt, dd in zip(dts, dds):
            chave = _clean_text(dt.get_text(" ", strip=True)).lower()
            valor = _clean_text(dd.get_text(" ", strip=True))
            if chave and valor and chave not in specs:
                specs[chave] = valor

    return specs


def classificar_pagina(html: str, url: str = "") -> Dict[str, object]:
    soup = BeautifulSoup(html or "", "html.parser")
    texto = (soup.get_text(" ", strip=True) or "").lower()
    json_ld = _parse_json_ld(soup)

    score_produto = 0
    score_categoria = 0
    url_baixa = (url or "").lower()

    if json_ld.get("nome"):
        score_produto += 4
    if json_ld.get("preco"):
        score_produto += 3
    if json_ld.get("gtin"):
        score_produto += 2
    if _extract_meta(soup, "og:type").lower() == "product":
        score_produto += 3
    if any(token in url_baixa for token in PRODUCT_URL_HINTS):
        score_produto += 2
    if any(token in texto for token in ("comprar", "adicionar ao carrinho", "sku", "ean", "gtin")):
        score_produto += 1

    quantidade_links = len(soup.find_all("a", href=True))
    if quantidade_links >= 12:
        score_categoria += 1
    if any(token in url_baixa for token in CATEGORY_URL_HINTS):
        score_categoria += 2
    if any(token in texto for token in ("categorias", "departamentos", "coleções", "colecoes")):
        score_categoria += 2
    if soup.find(attrs={"aria-label": re.compile("breadcrumb", re.I)}):
        score_categoria += 1

    return {
        "is_product": score_produto >= 4 and score_produto >= score_categoria,
        "is_category": score_categoria >= 2 and score_categoria >= score_produto,
        "score_product": score_produto,
        "score_category": score_categoria,
    }


def extrair_produto_html(html: str, url: str) -> Dict:
    soup = BeautifulSoup(html or "", "html.parser")
    json_ld = _parse_json_ld(soup)
    specs = _extract_specs_map(soup)

    titulo = _pick_first(
        json_ld.get("nome", ""),
        _extract_meta(soup, "og:title"),
        _find_candidate_text(soup, ["h1", "[class*=product-name]", "[class*=product_title]", "[itemprop=name]"]),
        soup.title.get_text(" ", strip=True) if soup.title else "",
    )

    descricao = _pick_first(
        json_ld.get("descricao_curta", ""),
        _extract_meta(soup, "og:description"),
        _extract_meta(soup, "description"),
        _find_candidate_text(soup, ["[class*=description]", "[itemprop=description]"]),
    )

    imagens_lista = json_ld.get("imagens") or []
    if not isinstance(imagens_lista, list):
        imagens_lista = [_clean_text(imagens_lista)] if _clean_text(imagens_lista) else []

    imagens_jsonld: List[str] = []
    for img_url in imagens_lista:
        _adicionar_url_imagem(
            urls=imagens_jsonld,
            url=img_url,
            base_url=url,
            contexto="json-ld",
            min_score=1,
        )

    imagens_html = _collect_images(soup, url)

    imagens: List[str] = []
    for lista in (imagens_jsonld, imagens_html):
        for item in lista:
            img = _clean_text(item)
            if img and img not in imagens:
                imagens.append(img)

    preco = _pick_first(
        json_ld.get("preco", ""),
        _extract_meta(soup, "product:price:amount"),
        _extract_meta(soup, "price"),
        _find_candidate_text(soup, ["[class*=price]", "[data-price]", "[itemprop=price]"]),
        _find_price_in_text(html),
    )
    preco = _to_price(preco)
