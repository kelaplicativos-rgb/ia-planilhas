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
    r'Avaliacoes?',
    r'Ainda não há avaliações para este produto',
    r'Ainda nao ha avaliacoes para este produto',
    r'Ainda não há para este produto',
    r'Ainda nao ha para este produto',
    r'Seja o primeiro a avaliar este produto',
    r'Entre para avaliar',
    r'Calcule o frete',
    r'Continuar comprando',
]

CUT_MARKER_PATTERNS = [
    r'\bAvaliaç(?:ão|ões)\b.*$',
    r'\bAvaliac(?:ao|oes)\b.*$',
    r'\bAinda\s+n[ãa]o\s+h[áa](?:\s+avaliaç(?:ão|ões)|\s+avaliac(?:ao|oes))?\s+(?:para|deste|desse|neste|nesse).*$',
    r'\bSeja\s+o\s+primeiro\s+a\s+avaliar\b.*$',
    r'\bEntre\s+para\s+avaliar\b.*$',
    r'\bProdutos\s+relacionados\b.*$',
    r'\bQuem\s+viu\s+tamb[eé]m\s+comprou\b.*$',
    r'\bCompartilhar\s+produto\b.*$',
    r'\bCalcule\s+o\s+frete\b.*$',
]

LEADING_LABEL_PATTERNS = [
    r'^(?:descriç(?:ão|ao)|descricao)(?:\s+do\s+produto|\s+completa)?\s*[:\-–—|•]*\s*',
    r'^(?:detalhes|detalhes\s+do\s+produto)\s*[:\-–—|•]*\s*',
]

DROP_SEGMENT_TERMS = [
    'produtos', 'carrinho', 'minha conta', 'login', 'newsletter', 'whatsapp',
    'politica de privacidade', 'política de privacidade', 'termos de uso',
    'formas de pagamento', 'atendimento', 'fale conosco', 'todos os direitos reservados',
    'avaliacoes', 'avaliações', 'ainda nao ha para este produto', 'ainda não há para este produto',
]

PLACEHOLDER_RE = re.compile(r'\b[A-Za-zÀ-ÿ /]+:\s*-{2,}\b')


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r'\s+', ' ', clean_cell(text)).strip()
    text = re.sub(r'\s*•\s*', '. ', text)
    parts = re.split(r'(?<=[.!?])\s+|\s{2,}', text)
    if len(parts) <= 1:
        parts = re.split(r'\s+-\s+|\s+\|\s+', text)
    return [clean_cell(part) for part in parts if clean_cell(part)]


def _cut_after_non_description_sections(text: str) -> str:
    out = clean_cell(text)
    if not out:
        return ''
    for pattern in CUT_MARKER_PATTERNS:
        out = re.sub(pattern, ' ', out, flags=re.I | re.S)
    return re.sub(r'\s+', ' ', out).strip()


def _remove_leading_labels(text: str) -> str:
    out = clean_cell(text)
    previous = None
    while previous != out:
        previous = out
        for pattern in LEADING_LABEL_PATTERNS:
            out = re.sub(pattern, '', out, flags=re.I).strip()
    return out


def _remove_repeated_title_tail(text: str, title: str = '') -> str:
    out = clean_cell(text)
    title_clean = clean_cell(title)
    if not out or not title_clean:
        return out

    title_key = normalize_key(title_clean)
    if not title_key:
        return out

    # Remove título repetido no fim, comum quando o bloco de descrição invade
    # cards/abas seguintes da página.
    for _ in range(3):
        out_key = normalize_key(out)
        if out_key == title_key:
            return ''
        escaped = re.escape(title_clean)
        new_out = re.sub(rf'(?:\s*[\-–—|•,.]*)\s*{escaped}\s*$', '', out, flags=re.I).strip()
        if new_out == out:
            break
        out = new_out
    return out


def _remove_noise(text: str) -> str:
    out = clean_cell(text)
    out = _cut_after_non_description_sections(out)
    out = _remove_leading_labels(out)
    for pattern in NOISE_PATTERNS:
        out = re.sub(pattern, ' ', out, flags=re.I)
    out = PLACEHOLDER_RE.sub(' ', out)
    out = _remove_leading_labels(out)
    out = re.sub(r'\s+', ' ', out)
    return out.strip(' -•|,.;')


def clean_product_description(text: str, title: str = '', limit: int = 1200) -> str:
    """Limpa descrição bruta capturada do site antes do mapeamento.

    Não inventa informação. Só remove ruído, repetições, preço, botões,
    avaliações, títulos duplicados e cabeçalho/rodapé. Funciona como uma camada
    de blindagem local para deixar a descrição complementar pronta para o Bling.
    """
    raw = _remove_noise(text)
    raw = _remove_repeated_title_tail(raw, title)
    title_key = normalize_key(title)
    result: list[str] = []
    seen: set[str] = set()

    for part in _split_sentences(raw):
        part = _remove_noise(part)
        part = _remove_repeated_title_tail(part, title)
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
    cleaned = _remove_repeated_title_tail(cleaned, title)
    cleaned = _remove_leading_labels(cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned[:limit].strip(' -•|,.;')
