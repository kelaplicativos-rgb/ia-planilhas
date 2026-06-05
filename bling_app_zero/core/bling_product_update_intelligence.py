from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_product_update_intelligence.py'

ACTION_UPDATE = 'ATUALIZAR'
ACTION_SKIP = 'PULAR'
ACTION_PENDING = 'PENDENCIA'
ACTION_CREATE = 'CADASTRAR'

IMPORTANT_FIELDS = (
    'nome',
    'descricao',
    'descricao_curta',
    'preco',
    'estoque',
    'codigo',
    'sku',
    'gtin',
    'marca',
    'categoria',
    'imagens',
    'ncm',
    'cest',
    'origem',
    'peso_liquido',
    'peso_bruto',
    'largura',
    'altura',
    'profundidade',
    'url',
)

RICH_FIELDS = {'descricao', 'descricao_curta', 'marca', 'categoria', 'imagens', 'ncm', 'cest', 'peso_liquido', 'peso_bruto', 'largura', 'altura', 'profundidade'}
IDENTITY_FIELDS = {'codigo', 'sku', 'gtin'}
PROTECTED_FIELDS = {'codigo', 'sku', 'gtin'}
MIN_CREATE_QUALITY = 68
MIN_UPDATE_QUALITY = 60
MIN_UPDATE_BENEFIT = 12

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    'nome': ('nome', 'titulo', 'título', 'produto', 'descricao produto', 'descrição produto'),
    'descricao': ('descricao complementar', 'descrição complementar', 'descricao longa', 'descrição longa', 'descricao', 'descrição', 'detalhes', 'caracteristicas', 'características'),
    'descricao_curta': ('descricao curta', 'descrição curta', 'resumo', 'short_description'),
    'preco': ('preco', 'preço', 'valor', 'price', 'preco venda', 'preço venda', 'preço unitário', 'preco unitario'),
    'estoque': ('estoque', 'quantidade', 'qtd', 'saldo', 'balanco', 'balanço', 'stock'),
    'codigo': ('codigo', 'código', 'sku', 'referencia', 'referência', 'code', 'cod produto'),
    'sku': ('sku', 'codigo', 'código', 'referencia', 'referência'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean'),
    'marca': ('marca', 'brand', 'fabricante'),
    'categoria': ('categoria', 'category', 'departamento', 'grupo'),
    'imagens': ('imagens', 'imagem', 'fotos', 'foto', 'image', 'images', 'url imagem', 'url imagens'),
    'ncm': ('ncm',),
    'cest': ('cest',),
    'origem': ('origem', 'origem produto', 'origem do produto'),
    'peso_liquido': ('peso liquido', 'peso líquido', 'peso_liquido', 'peso líquido kg', 'peso liquido kg'),
    'peso_bruto': ('peso bruto', 'peso_bruto', 'peso bruto kg'),
    'largura': ('largura', 'width', 'largura cm'),
    'altura': ('altura', 'height', 'altura cm'),
    'profundidade': ('profundidade', 'comprimento', 'depth', 'length', 'profundidade cm', 'comprimento cm'),
    'url': ('url', 'link', 'produto url', 'url produto'),
}


@dataclass(frozen=True)
class ProductUpdateDecision:
    action: str
    should_update: bool
    should_skip: bool
    should_create: bool
    should_hold: bool
    reason: str
    changed_fields: tuple[str, ...]
    payload: dict[str, Any]
    quality_score: int
    risk: str
    site_identity: str
    bling_identity: str
    benefit_score: int = 0
    rich_fields: tuple[str, ...] = tuple()
    missing_quality_fields: tuple[str, ...] = tuple()
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['changed_fields'] = list(self.changed_fields)
        data['rich_fields'] = list(self.rich_fields)
        data['missing_quality_fields'] = list(self.missing_quality_fields)
        return data


def _clean_key(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ç', 'c').replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i').replace('ó', 'o').replace('ô', 'o').replace('õ', 'o').replace('ú', 'u')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _clean_text(value: object) -> str:
    if value is None:
        return ''
    text = str(value).replace('\u200b', '').replace('\ufeff', '').strip()
    if text.lower() in {'nan', 'none', 'null'}:
        return ''
    return re.sub(r'\s+', ' ', text).strip()


def _row_get(row: Mapping[str, Any] | Any, canonical: str) -> str:
    if row is None:
        return ''
    aliases = _FIELD_ALIASES.get(canonical, (canonical,))
    try:
        items = row.items() if isinstance(row, Mapping) else row.to_dict().items()
    except Exception:
        return ''
    normalized = {_clean_key(key): value for key, value in items}
    for alias in aliases:
        key = _clean_key(alias)
        if key in normalized:
            return _clean_text(normalized[key])
    for alias in aliases:
        needle = _clean_key(alias)
        for key, value in normalized.items():
            if needle and needle in key:
                return _clean_text(value)
    return ''


def _money(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ''
    text = re.sub(r'[^0-9,.-]+', '', text)
    if not text:
        return ''
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return str(Decimal(text).quantize(Decimal('0.01')))
    except (InvalidOperation, ValueError):
        return ''


def _number(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ''
    match = re.search(r'-?\d+(?:[,.]\d+)?', text)
    if not match:
        return ''
    return match.group(0).replace(',', '.')


def _gtin(value: object) -> str:
    digits = re.sub(r'\D+', '', _clean_text(value))
    return digits if len(digits) in {8, 12, 13, 14} else ''


def _images(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ''
    parts = [part.strip() for part in re.split(r'[;,|\n]+', text) if part.strip()]
    clean: list[str] = []
    seen: set[str] = set()
    blocked = ('logo', 'placeholder', 'sem-imagem', 'semimagem', 'no-image', 'favicon', 'sprite', 'icon', 'whatsapp', 'instagram', 'facebook')
    for part in parts:
        low = part.lower()
        if not low.startswith(('http://', 'https://')):
            continue
        if any(term in low for term in blocked):
            continue
        normalized = re.sub(r'([?&])(v|cache|width|height|w|h|resize|quality)=[^&]+', '', part, flags=re.I).rstrip('?&')
        if normalized not in seen:
            clean.append(normalized)
            seen.add(normalized)
    return '|'.join(clean[:10])


def normalize_product_payload(row: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in IMPORTANT_FIELDS:
        raw = _row_get(row, field)
        if field == 'preco':
            value = _money(raw)
        elif field in {'estoque', 'peso_liquido', 'peso_bruto', 'largura', 'altura', 'profundidade'}:
            value = _number(raw)
        elif field == 'gtin':
            value = _gtin(raw)
        elif field == 'imagens':
            value = _images(raw)
        elif field in {'ncm'}:
            digits = re.sub(r'\D+', '', raw)
            value = digits if len(digits) == 8 else ''
        elif field in {'cest'}:
            digits = re.sub(r'\D+', '', raw)
            value = digits if len(digits) == 7 else ''
        elif field == 'origem':
            digits = re.sub(r'\D+', '', raw)
            value = digits[:1] if digits else ''
        else:
            value = _clean_text(raw)
        if value:
            payload[field] = value
    return payload


def _identity(payload: Mapping[str, Any]) -> str:
    for field in ('codigo', 'sku', 'gtin'):
        value = _clean_text(payload.get(field))
        if value:
            return value
    return ''


def _similar_text(a: object, b: object) -> bool:
    left = _clean_key(a)
    right = _clean_key(b)
    if left == right:
        return True
    if not left or not right:
        return False
    return left in right or right in left


def _same_value(field: str, site_value: object, bling_value: object) -> bool:
    if field == 'preco':
        return _money(site_value) == _money(bling_value)
    if field in {'estoque', 'peso_liquido', 'peso_bruto', 'largura', 'altura', 'profundidade'}:
        return _number(site_value) == _number(bling_value)
    if field == 'gtin':
        return _gtin(site_value) == _gtin(bling_value)
    if field == 'imagens':
        return _images(site_value) == _images(bling_value)
    return _similar_text(site_value, bling_value)


def _text_quality(value: object) -> int:
    text = _clean_text(value)
    if not text:
        return 0
    words = re.findall(r'[A-Za-zÀ-ÿ0-9]{2,}', text)
    score = min(len(text), 3500) + min(len(words), 400) * 4
    if re.match(r'^(produto|produto sem nome|sem nome|item)\b', text, flags=re.I):
        score -= 160
    return max(score, 0)


def _quality_score(payload: Mapping[str, Any]) -> int:
    score = 100
    if not _identity(payload):
        score -= 35
    if not payload.get('nome'):
        score -= 20
    if not payload.get('preco'):
        score -= 12
    if not payload.get('imagens'):
        score -= 10
    if not payload.get('descricao') and not payload.get('descricao_curta'):
        score -= 12
    if not payload.get('marca'):
        score -= 5
    if not payload.get('categoria'):
        score -= 5
    if payload.get('descricao') and _text_quality(payload.get('descricao')) < 80:
        score -= 5
    return max(0, min(100, score))


def _missing_quality_fields(payload: Mapping[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    for field in ('nome', 'preco', 'descricao', 'imagens', 'marca', 'categoria'):
        if field == 'descricao':
            if not payload.get('descricao') and not payload.get('descricao_curta'):
                missing.append(field)
            continue
        if not payload.get(field):
            missing.append(field)
    return tuple(missing)


def _benefit_score(changed: list[str], site_payload: Mapping[str, Any], bling_payload: Mapping[str, Any]) -> int:
    weights = {
        'descricao': 30,
        'descricao_curta': 28,
        'imagens': 28,
        'categoria': 18,
        'marca': 14,
        'preco': 12,
        'ncm': 8,
        'cest': 6,
        'origem': 6,
        'peso_liquido': 7,
        'peso_bruto': 7,
        'largura': 6,
        'altura': 6,
        'profundidade': 6,
    }
    score = 0
    for field in changed:
        score += weights.get(field, 4)
        if not bling_payload.get(field) and site_payload.get(field):
            score += 8
    return score


def _safe_changed_fields(site_payload: Mapping[str, Any], bling_payload: Mapping[str, Any]) -> tuple[list[str], dict[str, Any]]:
    changed: list[str] = []
    final_payload: dict[str, Any] = {}
    for field, site_value in site_payload.items():
        if field == 'url':
            final_payload[field] = site_value
            continue
        bling_value = bling_payload.get(field, '')
        if field in PROTECTED_FIELDS and bling_value:
            continue
        if not _same_value(field, site_value, bling_value):
            changed.append(field)
            final_payload[field] = site_value
    return changed, final_payload


def analyze_product_update_need(site_product: Mapping[str, Any] | Any, bling_product: Mapping[str, Any] | Any | None) -> ProductUpdateDecision:
    site_payload = normalize_product_payload(site_product)
    bling_payload = normalize_product_payload(bling_product or {})
    site_id = _identity(site_payload)
    bling_id = _identity(bling_payload)
    score = _quality_score(site_payload)
    missing = _missing_quality_fields(site_payload)
    rich = tuple(field for field in RICH_FIELDS if site_payload.get(field))

    if not site_id and not site_payload.get('nome'):
        return ProductUpdateDecision(ACTION_PENDING, False, False, False, True, 'Produto do site sem SKU/código/GTIN e sem nome confiável para localizar ou cadastrar.', tuple(), site_payload, score, 'alto', site_id, bling_id, 0, rich, missing)

    if not bling_product:
        if score < MIN_CREATE_QUALITY:
            return ProductUpdateDecision(ACTION_PENDING, False, False, False, True, f'Produto extraído do site com qualidade insuficiente para envio automático ({score}/100). Falta: {", ".join(missing) or "dados ricos"}.', tuple(site_payload.keys()), site_payload, score, 'alto', site_id, bling_id, 0, rich, missing)
        return ProductUpdateDecision(ACTION_CREATE, False, False, True, False, 'Produto não encontrado no Bling; enviar para cadastro inteligente com dados enriquecidos do site.', tuple(site_payload.keys()), site_payload, score, 'baixo' if score >= 82 else 'medio', site_id, bling_id, _benefit_score(list(site_payload.keys()), site_payload, {}), rich, missing)

    changed, final_payload = _safe_changed_fields(site_payload, bling_payload)
    benefit = _benefit_score(changed, site_payload, bling_payload)

    if not changed:
        return ProductUpdateDecision(ACTION_SKIP, False, True, False, False, 'Produto já está atualizado no Bling; nenhuma mudança real detectada.', tuple(), {}, score, 'baixo', site_id, bling_id, 0, rich, missing)

    if score < MIN_UPDATE_QUALITY:
        return ProductUpdateDecision(ACTION_PENDING, False, False, False, True, f'Mudanças detectadas ({", ".join(changed)}), mas a qualidade do site está baixa para atualizar automaticamente ({score}/100).', tuple(changed), final_payload, score, 'alto', site_id, bling_id, benefit, rich, missing)

    if benefit < MIN_UPDATE_BENEFIT and not (set(changed) & RICH_FIELDS):
        return ProductUpdateDecision(ACTION_SKIP, False, True, False, False, f'Mudança pequena detectada ({", ".join(changed)}), mas não compensa chamar a API do Bling.', tuple(changed), {}, score, 'baixo', site_id, bling_id, benefit, rich, missing)

    risk = 'baixo'
    if score < 72:
        risk = 'medio'
    if any(field in changed for field in ('gtin', 'codigo', 'sku')):
        risk = 'medio'

    return ProductUpdateDecision(ACTION_UPDATE, True, False, False, False, f'Atualização necessária e compensadora: {", ".join(changed)}. Benefício {benefit}.', tuple(changed), final_payload, score, risk, site_id, bling_id, benefit, tuple(field for field in rich if field in changed or field in final_payload), missing)


__all__ = [
    'ACTION_CREATE',
    'ACTION_PENDING',
    'ACTION_SKIP',
    'ACTION_UPDATE',
    'ProductUpdateDecision',
    'analyze_product_update_need',
    'normalize_product_payload',
]
