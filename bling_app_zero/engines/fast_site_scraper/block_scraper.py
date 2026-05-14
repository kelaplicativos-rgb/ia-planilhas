from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup, Tag

from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.engines.fast_site_scraper.models import FastProductPage
from bling_app_zero.engines.fast_site_scraper.page_parser import soup_from_page

NOISE_TERMS = [
    'carrinho', 'minha conta', 'entrar', 'login', 'cadastre se', 'newsletter', 'whatsapp',
    'facebook', 'instagram', 'youtube', 'tiktok', 'politica de privacidade', 'política de privacidade',
    'termos de uso', 'trocas e devolucoes', 'trocas e devoluções', 'formas de pagamento',
    'atendimento', 'central de atendimento', 'fale conosco', 'copyright', 'todos os direitos reservados',
    'produto adicionado', 'comprar agora', 'adicionar ao carrinho', 'continuar comprando',
    'calcule o frete', 'cep', 'departamentos', 'categorias', 'menu', 'home', 'inicio', 'início',
    'buscar', 'pesquisar', 'favoritos', 'compare', 'compartilhar', 'voltar ao topo',
]

PRODUCT_SIGNAL_TERMS = [
    'descricao', 'descrição', 'descricao completa', 'descrição completa', 'descricao do produto', 'descrição do produto',
    'detalhes', 'detalhes do produto', 'informacoes adicionais', 'informações adicionais',
    'caracteristicas', 'características', 'especificacoes', 'especificações', 'ficha tecnica', 'ficha técnica',
    'codigo', 'código', 'sku', 'referencia', 'referência', 'modelo', 'marca', 'ean', 'gtin', 'ncm',
    'garantia', 'conteudo da embalagem', 'conteúdo da embalagem', 'produto', 'hifi', 'fone',
]

BLOCK_SELECTORS = [
    '[itemprop=description]', '[data-product-description]', '[data-testid*=description]', '[data-testid*=descricao]',
    '[class*=description]', '[class*=descricao]', '[class*=descri]', '[class*=detalhe]', '[class*=detail]',
    '[id*=description]', '[id*=descricao]', '[id*=descri]', '[id*=detalhe]', '[id*=detail]',
    '.description', '.descricao', '.descricao-produto', '.product-description', '.productDescription',
    '.product-details', '.product-tabs', '.tabs', '.tab-content', '.product-info', '.produto-info',
    '.informacoes', '.informacoes-adicionais', '.info-adicional', '.additional-information',
    '.specifications', '.specification', '.especificacoes', '.ficha-tecnica', '.caracteristicas',
    '#descricao', '#description', '#detalhes', '#especificacoes', '#ficha-tecnica',
    'section[class*=product]', 'div[class*=product]', 'main', 'article',
]

META_DESCRIPTION_SELECTORS = [
    'meta[name="description"]',
    'meta[property="og:description"]',
    'meta[name="twitter:description"]',
]

REMOVE_SELECTORS = [
    'script', 'style', 'noscript', 'svg', 'canvas', 'iframe', 'header', 'footer', 'nav', 'aside',
    '.menu', '.navbar', '.nav', '.breadcrumb', '.breadcrumbs', '.newsletter', '.whatsapp',
    '.social', '.share', '.cart', '.carrinho', '.login', '.account', '.minha-conta', '.rodape', '.footer',
    '.header', '.topo', '.modal', '.popup', '.cookie', '.cookies', '.lgpd', '.banner', '.ads', '.advertisement',
]


@dataclass(frozen=True)
class BlockScrapeResult:
    complementary_description: str = ''
    technical_sheet: str = ''
    attributes: str = ''
    all_blocks: str = ''


def _dedupe_keep_order(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_cell(value)
        key = normalize_key(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _remove_noise_nodes(soup: BeautifulSoup) -> None:
    for selector in REMOVE_SELECTORS:
        for node in soup.select(selector):
            try:
                node.decompose()
            except Exception:
                pass


def _is_noise_text(text: str) -> bool:
    key = normalize_key(text)
    if not key:
        return True
    if len(key) < 12:
        return True
    if any(term in key for term in [normalize_key(t) for t in NOISE_TERMS]):
        if not any(signal in key for signal in [normalize_key(t) for t in PRODUCT_SIGNAL_TERMS]):
            return True
    words = key.split()
    if len(words) <= 2 and not any(signal in key for signal in [normalize_key(t) for t in PRODUCT_SIGNAL_TERMS]):
        return True
    if len(text) > 9000:
        return True
    return False


def _score_text(text: str) -> int:
    key = normalize_key(text)
    score = 0
    for term in PRODUCT_SIGNAL_TERMS:
        if normalize_key(term) in key:
            score += 18
    if re.search(r'[:：]', text):
        score += 8
    if re.search(r'\b[A-Z0-9][A-Z0-9._/-]{2,}\b', text):
        score += 4
    if 80 <= len(text) <= 4200:
        score += 14
    if len(text) > 4200:
        score += 4
    if any(normalize_key(term) in key for term in [normalize_key(t) for t in NOISE_TERMS]):
        score -= 25
    return score


def _node_text(node: Tag) -> str:
    chunks: list[str] = []
    for table in node.find_all('table'):
        rows: list[str] = []
        for tr in table.find_all('tr'):
            cells = [clean_cell(cell.get_text(' ', strip=True)) for cell in tr.find_all(['th', 'td'])]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(': '.join(cells) if len(cells) == 2 else ' | '.join(cells))
        if rows:
            chunks.append(' • '.join(rows))
    for li in node.find_all('li'):
        text = clean_cell(li.get_text(' ', strip=True))
        if text:
            chunks.append(text)
    direct = clean_cell(node.get_text(' ', strip=True))
    if direct:
        chunks.append(direct)
    return ' • '.join(_dedupe_keep_order(chunks))


def _meta_descriptions(soup: BeautifulSoup) -> list[str]:
    values: list[str] = []
    for selector in META_DESCRIPTION_SELECTORS:
        node = soup.select_one(selector)
        if node:
            text = clean_cell(node.get('content') or '')
            if text and not _is_noise_text(text):
                values.append(text)
    return values


def _candidate_blocks(page: FastProductPage) -> list[str]:
    soup = soup_from_page(page)
    _remove_noise_nodes(soup)
    blocks: list[str] = []
    blocks.extend(_meta_descriptions(soup))

    for selector in BLOCK_SELECTORS:
        for node in soup.select(selector):
            if isinstance(node, Tag):
                text = _node_text(node)
                if text and not _is_noise_text(text):
                    blocks.append(text)

    for heading in soup.find_all(['h2', 'h3', 'h4', 'strong', 'b', 'button', 'summary']):
        title = clean_cell(heading.get_text(' ', strip=True))
        title_key = normalize_key(title)
        if not any(normalize_key(term) in title_key for term in PRODUCT_SIGNAL_TERMS):
            continue
        parts = [title]
        parent = heading.parent if isinstance(heading.parent, Tag) else None
        if parent:
            parent_text = _node_text(parent)
            if parent_text and not _is_noise_text(parent_text):
                parts.append(parent_text)
        for sibling in heading.find_all_next(limit=10):
            if not isinstance(sibling, Tag):
                continue
            if sibling.name in {'h1', 'h2', 'h3'} and sibling is not heading:
                break
            text = _node_text(sibling)
            if text and not _is_noise_text(text):
                parts.append(text)
        blocks.append(' • '.join(_dedupe_keep_order(parts)))

    product = page.jsonld_products[0] if page.jsonld_products else {}
    if isinstance(product, dict):
        for key in ['description', 'additionalProperty', 'features', 'material', 'model', 'audience']:
            value = product.get(key)
            if isinstance(value, list):
                chunks = []
                for item in value:
                    if isinstance(item, dict):
                        name = clean_cell(item.get('name') or item.get('propertyID') or '')
                        val = clean_cell(item.get('value') or item.get('description') or '')
                        chunks.append(f'{name}: {val}' if name and val else name or val)
                    else:
                        chunks.append(clean_cell(item))
                text = ' • '.join(_dedupe_keep_order(chunks))
            elif isinstance(value, dict):
                text = ' • '.join(f'{k}: {v}' for k, v in value.items() if v)
            else:
                text = clean_cell(value)
            if text and not _is_noise_text(text):
                blocks.append(text)

    ranked = sorted(_dedupe_keep_order(blocks), key=_score_text, reverse=True)
    return [text for text in ranked if _score_text(text) > 0][:18]


def _split_technical(blocks: list[str]) -> tuple[str, str, str]:
    tech: list[str] = []
    attrs: list[str] = []
    desc: list[str] = []
    for block in blocks:
        key = normalize_key(block)
        if any(term in key for term in ['ficha tecnica', 'especificacoes', 'especificacao', 'informacoes tecnicas']):
            tech.append(block)
        elif any(term in key for term in ['caracteristicas', 'informacoes adicionais', 'detalhes', 'conteudo da embalagem']):
            attrs.append(block)
        else:
            desc.append(block)
    return (
        ' • '.join(_dedupe_keep_order(desc))[:7000],
        ' • '.join(_dedupe_keep_order(tech))[:5000],
        ' • '.join(_dedupe_keep_order(attrs))[:5000],
    )


def scrape_product_blocks(page: FastProductPage) -> BlockScrapeResult:
    blocks = _candidate_blocks(page)
    desc, tech, attrs = _split_technical(blocks)
    all_blocks = ' • '.join(_dedupe_keep_order(blocks))[:9000]
    if not desc:
        desc = all_blocks[:7000]
    return BlockScrapeResult(
        complementary_description=desc,
        technical_sheet=tech,
        attributes=attrs,
        all_blocks=all_blocks,
    )
