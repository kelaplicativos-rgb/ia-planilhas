from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_smart_enrichment.py'

GENERIC_CATEGORY_TERMS = {
    'home', 'inicio', 'início', 'loja', 'produto', 'produtos', 'catalogo', 'catálogo',
    'departamento', 'departamentos', 'categoria', 'categorias', 'todos', 'ofertas',
    'promocoes', 'promoções', 'mais vendidos', 'novidades', 'mega center', 'stoqui',
}

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('Teclados', ('teclado', 'keyboard', 'abnt', 'usb al-', 'multimidia')),
    ('Mouses', ('mouse', 'mice', 'dpi', 'optico', 'óptico', 'sem fio')),
    ('Fones de ouvido', ('fone', 'headset', 'earphone', 'auricular', 'bluetooth')),
    ('Caixas de som', ('caixa de som', 'speaker', 'subwoofer', 'soundbar')),
    ('Carregadores', ('carregador', 'charger', 'fonte usb', 'turbo', 'tomada usb')),
    ('Cabos e adaptadores', ('cabo', 'adaptador', 'hdmi', 'usb-c', 'tipo c', 'p2', 'p10', 'vga')),
    ('Capas e películas', ('capinha', 'capa ', 'pelicula', 'película', 'case')),
    ('Suportes', ('suporte', 'tripé', 'tripe', 'holder', 'base para')),
    ('Informática', ('notebook', 'computador', 'pc ', 'monitor', 'hub usb', 'webcam')),
    ('Eletrônicos', ('eletronico', 'eletrônico', 'digital', 'controle remoto', 'relogio', 'relógio')),
    ('Acessórios para celular', ('celular', 'smartphone', 'iphone', 'android', 'samsung', 'motorola')),
    ('Ferramentas', ('chave', 'alicate', 'furadeira', 'parafusadeira', 'solda')),
    ('Iluminação', ('lampada', 'lâmpada', 'led', 'refletor', 'luminaria', 'luminária')),
)

BAD_IMAGE_TERMS = (
    'logo', 'banner', 'placeholder', 'no-image', 'no_image', 'sem-imagem', 'semimagem',
    'favicon', 'sprite', 'icon', 'icone', 'whatsapp', 'instagram', 'facebook', 'youtube',
    'loading', 'blank', 'default', 'avatar', 'marca-dagua', 'watermark'
)

GOOD_IMAGE_HINTS = (
    'produto', 'product', 'produtos', 'images', 'image', 'foto', 'fotos', 'uploads', 'catalog', 'catalogo'
)

NOISE_PATTERNS = (
    r'ainda\s+n[aã]o\s+h[aá]\s+para\s+este\s+produto',
    r'descri[cç][aã]o\s+do\s+produto',
    r'descri[cç][aã]o\s*:',
    r'caracter[ií]sticas\s*:',
    r'ficha\s+t[eé]cnica\s*:',
    r'clique\s+aqui',
    r'comprar\s+agora',
    r'adicionar\s+ao\s+carrinho',
    r'produto\s+indispon[ií]vel',
)

TEXT_FIXES: tuple[tuple[str, str], ...] = (
    (r'\bconexao\b', 'conexão'),
    (r'\bcompativel\b', 'compatível'),
    (r'\bpratico\b', 'prático'),
    (r'\bresistente\b', 'resistente'),
    (r'\bduravel\b', 'durável'),
    (r'\binstalacao\b', 'instalação'),
    (r'\butilizacao\b', 'utilização'),
    (r'\bqualidade\b', 'qualidade'),
    (r'\bmultimidia\b', 'multimídia'),
    (r'\bportatil\b', 'portátil'),
    (r'\botimo\b', 'ótimo'),
    (r'\bexcelente\b', 'excelente'),
)


@dataclass(frozen=True)
class EnrichmentResult:
    name: str
    description: str
    category: str
    image_urls: tuple[str, ...]
    confidence: int
    warnings: tuple[str, ...]
    description_short: str = ''
    description_complementary: str = ''


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o')
    text = text.replace('ú', 'u').replace('ç', 'c')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _clean_text(value: object, limit: int = 160) -> str:
    text = str(value or '').replace('\u200b', '').replace('\ufeff', '').strip()
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit]


def _digits_only(value: object) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def looks_like_code(value: object) -> bool:
    text = str(value or '').strip()
    digits = _digits_only(text)
    if len(digits) in {8, 12, 13, 14} and len(digits) >= max(6, len(text) - 2):
        return True
    return bool(re.fullmatch(r'[A-Z0-9._/-]{5,}', text.upper())) and not re.search(r'[a-zA-Z]{3,}\s+[a-zA-Z]{3,}', text)


def choose_product_name(*, name: object = '', description: object = '', code: object = '', gtin: object = '') -> str:
    candidates = [_clean_text(name, 120), _clean_text(description, 120), _clean_text(code, 80), _clean_text(gtin, 80)]
    for candidate in candidates[:2]:
        if candidate and not looks_like_code(candidate) and len(candidate) >= 3:
            return candidate
    for candidate in candidates:
        if candidate:
            return candidate
    return 'Produto sem nome'


def _strip_noise(text: str) -> str:
    out = str(text or '')
    for pattern in NOISE_PATTERNS:
        out = re.sub(pattern, ' ', out, flags=re.IGNORECASE)
    out = re.sub(r'\s+', ' ', out)
    out = re.sub(r'\s+([,.;:])', r'\1', out)
    return out.strip(' -|•·;:,.')


def _fix_text(text: str) -> str:
    out = str(text or '').strip()
    out = out.replace(' plug-and-play ', ' plug-and-play ')
    for pattern, replacement in TEXT_FIXES:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    out = re.sub(r'\s+', ' ', out).strip()
    if out and not out.endswith(('.', '!', '?')):
        out += '.'
    if out:
        out = out[0].upper() + out[1:]
    return out


def _split_sentences(text: str) -> list[str]:
    raw = str(text or '')
    raw = re.sub(r'\s*(?:\||•|·|;|\n|\r)\s*', '. ', raw)
    pieces = [piece.strip(' -.,;:') for piece in re.split(r'(?<=[.!?])\s+|\.\s+', raw) if piece.strip(' -.,;:')]
    out: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        fixed = _fix_text(_strip_noise(piece))
        marker = _norm(fixed)
        if len(marker) < 4 or marker in seen:
            continue
        seen.add(marker)
        out.append(fixed)
    return out


def build_product_descriptions(*, name: object = '', short_description: object = '', complementary_description: object = '') -> tuple[str, str]:
    final_name = _clean_text(name, 140)
    raw_short = _strip_noise(str(short_description or ''))
    raw_complement = _strip_noise(str(complementary_description or ''))
    combined = ' '.join(part for part in (raw_short, raw_complement) if part).strip()
    if not combined or looks_like_code(combined):
        return '', ''

    sentences = _split_sentences(combined)
    name_norm = _norm(final_name)
    filtered: list[str] = []
    for sentence in sentences:
        sentence_norm = _norm(sentence)
        if name_norm and sentence_norm == name_norm:
            continue
        if sentence_norm in {'descricao', 'descricao do produto', 'produto'}:
            continue
        filtered.append(sentence)

    if not filtered:
        return '', ''

    short = filtered[0]
    if len(short) > 240:
        short = short[:237].rstrip(' ,;:.') + '...'
    complement_items = filtered[1:8]
    if not complement_items and len(filtered[0]) <= 240:
        complement = ''
    else:
        complement_source = filtered if len(filtered[0]) > 240 else complement_items
        complement = '\n'.join(f'- {item}' for item in complement_source if item)
    if len(complement) > 1800:
        complement = complement[:1797].rstrip() + '...'
    return short, complement


def clean_description(description: object, *, fallback_name: object = '') -> str:
    desc = _clean_text(description, 1000)
    name = _clean_text(fallback_name, 120)
    if not desc or looks_like_code(desc):
        return ''
    if name and _norm(desc) == _norm(name):
        return ''
    short, _complement = build_product_descriptions(name=name, short_description=desc)
    return short


def _split_category(raw: object) -> list[str]:
    text = str(raw or '').strip()
    if not text:
        return []
    parts = [part.strip(' -\t\n\r') for part in re.split(r'\s*(?:>|/|\\|\||;|»|›)\s*', text) if part.strip()]
    return parts or [text]


def clean_category(raw_category: object, *, title: object = '', description: object = '') -> str:
    parts = _split_category(raw_category)
    useful = [part for part in parts if _norm(part) and _norm(part) not in {_norm(term) for term in GENERIC_CATEGORY_TERMS}]
    if useful:
        for part in reversed(useful):
            normalized = _norm(part)
            if len(normalized) >= 3 and not looks_like_code(part):
                return _clean_text(part, 80)

    haystack = _norm(f'{title} {description}')
    for category, terms in CATEGORY_RULES:
        if any(_norm(term) in haystack for term in terms):
            return category
    return ''


def image_score(url: str, *, title: object = '', category: object = '') -> int:
    value = str(url or '').strip()
    if not value.lower().startswith(('http://', 'https://')):
        return -100
    parsed = urlparse(value)
    path = f'{parsed.netloc}/{parsed.path}'.lower()
    score = 20
    if re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', value.lower()):
        score += 25
    if any(term in path for term in GOOD_IMAGE_HINTS):
        score += 20
    if any(term in path for term in BAD_IMAGE_TERMS):
        score -= 80
    if '@' in path and not re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', value.lower()):
        score -= 45
    title_terms = [term for term in _norm(title).split() if len(term) >= 4][:6]
    category_terms = [term for term in _norm(category).split() if len(term) >= 4][:4]
    for term in title_terms + category_terms:
        if term in _norm(path):
            score += 4
    if any(size in path for size in ('thumb', 'thumbnail', 'small', 'mini')):
        score -= 8
    return score


def choose_image_urls(raw_images: object, *, title: object = '', category: object = '', limit: int = 5) -> tuple[str, ...]:
    urls: list[str] = []
    for piece in re.split(r'[|,;\n]+', str(raw_images or '')):
        url = piece.strip()
        if url and url not in urls:
            urls.append(url)
    ranked = sorted(((image_score(url, title=title, category=category), url) for url in urls), reverse=True)
    selected = [url for score, url in ranked if score >= 15]
    return tuple(selected[:limit])


def enrich_product_payload_fields(
    *,
    name: object = '',
    description: object = '',
    description_short: object = '',
    description_complementary: object = '',
    code: object = '',
    gtin: object = '',
    category: object = '',
    images: object = '',
) -> EnrichmentResult:
    final_name = choose_product_name(name=name, description=description or description_short or description_complementary, code=code, gtin=gtin)
    short, complement = build_product_descriptions(
        name=final_name,
        short_description=description_short or description,
        complementary_description=description_complementary,
    )
    final_category = clean_category(category, title=final_name, description=' '.join([short, complement]))
    final_images = choose_image_urls(images, title=final_name, category=final_category)
    confidence = 40
    warnings: list[str] = []
    if final_name and not looks_like_code(final_name):
        confidence += 20
    else:
        warnings.append('nome_parece_codigo')
    if final_category:
        confidence += 20
    else:
        warnings.append('categoria_nao_inferida')
    if final_images:
        confidence += 15
    else:
        warnings.append('imagem_nao_confiavel')
    if short:
        confidence += 5
    else:
        warnings.append('descricao_curta_nao_confiavel')
    if complement:
        confidence += 5
    return EnrichmentResult(final_name, short, final_category, final_images, min(100, confidence), tuple(warnings), short, complement)


__all__ = [
    'EnrichmentResult',
    'build_product_descriptions',
    'choose_image_urls',
    'choose_product_name',
    'clean_category',
    'clean_description',
    'enrich_product_payload_fields',
    'image_score',
    'looks_like_code',
]
