marca = _pick_first(
        json_ld.get("marca", ""),
        _extract_meta(soup, "product:brand"),
        specs.get("marca", ""),
        specs.get("brand", ""),
    )

    codigo = _pick_first(
        json_ld.get("codigo", ""),
        specs.get("sku", ""),
        specs.get("código", ""),
        specs.get("codigo", ""),
        specs.get("ref", ""),
        specs.get("referência", ""),
    )

    gtin = _pick_first(
        json_ld.get("gtin", ""),
        specs.get("ean", ""),
        specs.get("gtin", ""),
        specs.get("código de barras", ""),
        _find_gtin_in_text(html),
    )
    gtin = _only_digits(gtin)

    disponibilidade = _pick_first(
        json_ld.get("disponibilidade", ""),
        _extract_meta(soup, "product:availability"),
        _find_candidate_text(soup, ["[class*=stock]", "[class*=availability]", "[class*=dispon]"]),
    )

    categoria = _pick_first(
        json_ld.get("categoria", ""),
        _extract_breadcrumb_category(soup),
    )

    ncm = _pick_first(
        specs.get("ncm", ""),
        specs.get("classificação fiscal", ""),
        specs.get("classificacao fiscal", ""),
    )

    unidade = _pick_first(
        specs.get("unidade", ""),
        specs.get("un", ""),
        specs.get("medida", ""),
    )

    return {
        "origem_tipo": "scraper_url",
        "origem_arquivo_ou_url": url,
        "codigo": codigo,
        "descricao": titulo,
        "descricao_curta": descricao or titulo,
        "nome": titulo,
        "preco": preco,
        "preco_custo": preco,
        "estoque": "",
        "gtin": gtin,
        "marca": marca,
        "categoria": categoria,
        "ncm": ncm,
        "cest": _pick_first(specs.get("cest", "")),
        "cfop": "",
        "unidade": unidade,
        "fornecedor": "",
        "cnpj_fornecedor": "",
        "imagens": " | ".join([_clean_text(x) for x in imagens if _clean_text(x)]),
        "disponibilidade_site": disponibilidade,
    }


def extrair_produtos_de_urls(urls: List[str], baixar_html_func) -> pd.DataFrame:
    linhas: List[Dict] = []

    for url in urls:
        resultado = baixar_html_func(url)

        if not resultado.get("ok"):
            linhas.append(
                {
                    "origem_tipo": "scraper_url",
                    "origem_arquivo_ou_url": url,
                    "codigo": "",
                    "descricao": "",
                    "descricao_curta": "",
                    "nome": "",
                    "preco": "",
                    "preco_custo": "",
                    "estoque": "",
                    "gtin": "",
                    "marca": "",
                    "categoria": "",
                    "ncm": "",
                    "cest": "",
                    "cfop": "",
                    "unidade": "",
                    "fornecedor": "",
                    "cnpj_fornecedor": "",
                    "imagens": "",
                    "disponibilidade_site": "",
                    "erro_scraper": resultado.get("erro", "Falha ao baixar HTML."),
                }
            )
            continue

        extraido = extrair_produto_html(resultado.get("html", ""), resultado.get("url", url))
        extraido["erro_scraper"] = ""
        linhas.append(extraido)

    return pd.DataFrame(linhas)
