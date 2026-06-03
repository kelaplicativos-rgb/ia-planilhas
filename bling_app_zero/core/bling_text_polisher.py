from __future__ import annotations

import re

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_text_polisher.py'

PROTECTED_TOKEN_RE = re.compile(
    r'(?:\b[A-Z]{1,6}[-_/]?[0-9]{2,}[A-Z0-9._/-]*\b|\b[0-9]{2,}[A-Z]{1,6}\b|\b\d+(?:[,.]\d+)?\s?(?:cm|mm|m|kg|g|w|v|mah|gb|tb|hz|mhz|ghz|a)\b|\bUSB(?:-[A-Z])?\b|\bHDMI\b|\bLED\b|\bP[23]\b|\b[A-Z]{2,}\d{1,}\b)',
    flags=re.IGNORECASE,
)

COMMON_FIXES: tuple[tuple[str, str], ...] = (
    (r'\bconexao\b', 'conexão'),
    (r'\binstalacao\b', 'instalação'),
    (r'\butilizacao\b', 'utilização'),
    (r'\bcompatibilidade\b', 'compatibilidade'),
    (r'\bcompativel\b', 'compatível'),
    (r'\bpratico\b', 'prático'),
    (r'\bpratica\b', 'prática'),
    (r'\botimo\b', 'ótimo'),
    (r'\botima\b', 'ótima'),
    (r'\bportatil\b', 'portátil'),
    (r'\bresistente\b', 'resistente'),
    (r'\bduravel\b', 'durável'),
    (r'\bmultimidia\b', 'multimídia'),
    (r'\bteclado numerico\b', 'teclado numérico'),
    (r'\bsem fio\b', 'sem fio'),
    (r'\bplug\s*-?\s*and\s*-?\s*play\b', 'plug-and-play'),
    (r'\bhome office\b', 'home office'),
    (r'\bescritorio\b', 'escritório'),
    (r'\bqualidade\b', 'qualidade'),
    (r'\bproduto novo\b', 'produto novo'),
    (r'\bfone de ouvido\b', 'fone de ouvido'),
    (r'\bcaixa de som\b', 'caixa de som'),
)

NOISE_REPLACEMENTS: tuple[str, ...] = (
    r'ainda\s+n[aã]o\s+h[aá]\s+para\s+este\s+produto',
    r'descri[cç][aã]o\s+do\s+produto',
    r'descri[cç][aã]o\s*:',
    r'caracter[ií]sticas\s*:',
    r'ficha\s+t[eé]cnica\s*:',
    r'comprar\s+agora',
    r'adicionar\s+ao\s+carrinho',
    r'clique\s+aqui',
    r'veja\s+mais',
    r'saiba\s+mais',
)

LOWER_WORDS = {'de', 'da', 'do', 'das', 'dos', 'para', 'com', 'sem', 'em', 'e', 'ou', 'a', 'o'}
UPPER_TOKENS = {'usb', 'hdmi', 'led', 'p2', 'p3', 'vga', 'wifi', 'wi-fi', 'bluetooth', 'rgb', 'type-c', 'tipo-c'}


def _protect_tokens(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        key = f'__TOK{len(protected)}__'
        protected[key] = match.group(0)
        return key

    return PROTECTED_TOKEN_RE.sub(repl, text), protected


def _restore_tokens(text: str, protected: dict[str, str]) -> str:
    out = text
    for key, value in protected.items():
        out = out.replace(key, value)
    return out


def _normalize_spaces(text: str) -> str:
    out = str(text or '').replace('\u200b', '').replace('\ufeff', '')
    out = out.replace('–', '-').replace('—', '-')
    out = re.sub(r'\s+', ' ', out)
    out = re.sub(r'\s+([,.;:!?])', r'\1', out)
    out = re.sub(r'([,.;:!?])(?=[^\s\n])', r'\1 ', out)
    # BLINGFIX: não transformar hífen simples em separador visual.
    # Isso preserva modelos e padrões técnicos como AL-507, USB-C, X-100 e Tipo-C.
    out = re.sub(r'\s*[|•·]+\s*', ' - ', out)
    out = re.sub(r'\s+-\s+', ' - ', out)
    return re.sub(r'\s+', ' ', out).strip(' -|•·\t\n\r')


def strip_product_noise(text: object) -> str:
    out = _normalize_spaces(str(text or ''))
    for pattern in NOISE_REPLACEMENTS:
        out = re.sub(pattern, ' ', out, flags=re.IGNORECASE)
    return _normalize_spaces(out)


def apply_common_fixes(text: str) -> str:
    protected_text, protected = _protect_tokens(text)
    out = protected_text
    for pattern, replacement in COMMON_FIXES:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    out = _restore_tokens(out, protected)
    return _normalize_spaces(out)


def title_case_product_name(text: object, *, limit: int = 120) -> str:
    cleaned = apply_common_fixes(strip_product_noise(text))
    if not cleaned:
        return ''
    protected_text, protected = _protect_tokens(cleaned)
    words = protected_text.split(' ')
    fixed_words: list[str] = []
    for index, word in enumerate(words):
        raw = word.strip()
        if not raw:
            continue
        low = raw.lower()
        if raw in protected:
            fixed_words.append(raw)
        elif low in UPPER_TOKENS:
            fixed_words.append(low.upper().replace('WI-FI', 'Wi-Fi').replace('TYPE-C', 'Type-C').replace('TIPO-C', 'Tipo-C'))
        elif index > 0 and low in LOWER_WORDS:
            fixed_words.append(low)
        elif len(raw) <= 2 and raw.isupper():
            fixed_words.append(raw)
        else:
            fixed_words.append(raw[:1].upper() + raw[1:].lower())
    out = _restore_tokens(' '.join(fixed_words), protected)
    out = _normalize_spaces(out)
    return out[:limit].rstrip(' -|•·,.;:')


def split_sentences(text: str) -> list[str]:
    raw = str(text or '')
    raw = re.sub(r'\s*(?:\||•|·|;|\n|\r)\s*', '. ', raw)
    parts = [part.strip(' -.,;:') for part in re.split(r'(?<=[.!?])\s+|\.\s+', raw) if part.strip(' -.,;:')]
    return parts


def polish_sentence(text: object) -> str:
    cleaned = apply_common_fixes(strip_product_noise(text))
    if not cleaned:
        return ''
    if cleaned:
        cleaned = cleaned[:1].upper() + cleaned[1:]
    if cleaned and not cleaned.endswith(('.', '!', '?')):
        cleaned += '.'
    return cleaned


def polish_product_description(text: object, *, title: object = '', limit: int = 3500) -> str:
    cleaned = strip_product_noise(text)
    if not cleaned:
        return ''
    title_norm = _normalize_spaces(str(title or '')).lower()
    sentences: list[str] = []
    seen: set[str] = set()
    for part in split_sentences(cleaned):
        polished = polish_sentence(part)
        marker = re.sub(r'\W+', '', polished.lower())
        if not marker or marker in seen:
            continue
        if title_norm and _normalize_spaces(polished).rstrip('.').lower() == title_norm:
            continue
        seen.add(marker)
        sentences.append(polished)
    out = ' '.join(sentences).strip()
    if len(out) > limit:
        out = out[: limit - 3].rstrip() + '...'
    return out


def polish_product_texts(*, title: object = '', description: object = '', description_extra: object = '') -> dict[str, str]:
    polished_title = title_case_product_name(title)
    full_description = ' '.join(part for part in (str(description or '').strip(), str(description_extra or '').strip()) if part)
    polished_description = polish_product_description(full_description, title=polished_title)
    return {
        'title': polished_title,
        'description': polished_description,
        'description_short': polished_description,
        'description_complementary': '',
    }


__all__ = [
    'apply_common_fixes',
    'polish_product_description',
    'polish_product_texts',
    'polish_sentence',
    'strip_product_noise',
    'title_case_product_name',
]
