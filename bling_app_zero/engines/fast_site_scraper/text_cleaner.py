from __future__ import annotations

import re

from bling_app_zero.core.text import clean_cell, normalize_key

NOISE_PATTERNS = [
    r'Produtos\s+[^•]{0,180}?\s+C[ÓO]D[:\s#-]+\S+',
    r'C[ÓO]D[:\s#-]+\S+',
    r'R\$\s*[0-9\.]+,[0-9]{2}',
    r'\b\d+\s*%\s*OFF\b',
    r'no Pix',
    r'no cartão',
    r'Veja como pagar',
    r'Em estoque',
    r'Esgotado',
    r'Adicionar',
    r'Comprar',
    r'Compartilhar produto',
    r'Avaliações?',
    r'Ainda não há avaliações para este produto',
    r'Entre para avaliar',
    r'Calcule o frete',
    r'Continuar comprando',
]

DROP_SEGMENT_TERMS = [
    'produtos', 'carrinho', 'minha conta', 'login', 'newsletter', 'whatsapp',
    'politica de privacidade', 'política de privacidade', 'termos de uso',
    'formas de pagamento', 'atendimento', 'fale conosco', 'todos os direitos reservados',
]

PLACEHOLDER_RE = re.compile(r'\b[A-Za-zÀ-ÿ /]+:\s*-{2,}\b')


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r'\s+', ' ', clean_cell(text)).strip()
    text = re.sub(r'\s*•\s*', '. ', text)
    parts = re.split(r'(?<=[.!?])\s+|\s{2,}', text)
    if len(parts) <= 1:
        parts = re.split(r'\s+-\s+|\s+\|\s+', text)
    return [clean_cell(part) for part in parts if clean_cell(part)]


def _remove_noise(text: str) -> str:
    out = clean_cell(text)
    for pattern in NOISE_PATTERNS:
        out = re.sub(pattern, ' ', out, flags=re.I)
    out = PLACEHOLDER_RE.sub(' ', out)
    out = re.sub(r'\s+', ' ', out)
    return out.strip(' -•|,.;')


def clean_product_description(text: str, title: str = '', limit: int = 1200) -> str:
    """Limpa descrição bruta capturada do site antes do mapeamento.

    Não inventa informação. Só remove ruído, repetições, preço, botões,
    avaliações e cabeçalho/rodapé. Funciona como uma camada de IA local para
    deixar a descrição complementar pronta para o Bling.
    """
    raw = _remove_noise(text)
    title_key = normalize_key(title)
    result: list[str] = []
    seen: set[str] = set()

    for part in _split_sentences(raw):
        part = _remove_noise(part)
        key = normalize_key(part)
        if not key or len(key) < 18:
            continue
        if title_key and key == title_key:
            continue
        if any(term in key for term in [normalize_key(t) for t in DROP_SEGMENT_TERMS]):
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(part)
        if len(' '.join(result)) >= limit:
            break

    cleaned = ' '.join(result).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned[:limit].strip(' -•|,.;')
