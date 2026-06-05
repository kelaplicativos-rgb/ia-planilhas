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
    'peso',
    'largura',
    'altura',
    'profundidade',
    'url',
)

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    'nome': ('nome', 'titulo', 'título', 'produto', 'descricao', 'descrição'),
    'descricao': ('descricao complementar', 'descrição complementar', 'descricao longa', 'descrição longa', 'descricao', 'descrição'),
    'descricao_curta': ('descricao curta', 'descrição curta', 'resumo', 'short_description'),
    'preco': ('preco', 'preço', 'valor', 'price', 'preco venda', 'preço venda'),
    'estoque': ('estoque', 'quantidade', 'qtd', 'saldo', 'balanco', 'balanço', 'stock'),
    'codigo': ('codigo', 'código', 'sku', 'referencia', 'referência', 'code'),
    'sku': ('sku', 'codigo', 'código', 'referencia', 'referência'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras'),
    'marca': ('marca', 'brand', 'fabricante'),
    'categoria': ('categoria', 'category', 'departamento'),
    'imagens': ('imagens', 'imagem', 'fotos', 'foto', 'image', 'images'),
    'peso': ('peso', 'weight'),
    'largura': ('largura', 'width'),
    'altura': ('altura', 'height'),
    'profundidade': ('profundidade', 'comprimento', 'depth', 'length'),
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
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['changed_fields'] = list(self.changed_fields)
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
    text = str(value).strip()
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
    blocked = ('logo', 'placeholder', 'sem-imagem', 'no-image', 'favicon')
    for part in parts:
        low = part.lower()
        if any(term in low for term in blocked):
            continue
        normalized = re.sub(r'([?&])(v|cache|width|height|w|h|resize|quality)=[^&]+', '', part, flags=re.I).rstrip('?&')
        if normalized not in seen:
            clean.append(normalized)
            seen.add(normalized)
    return '|'.join(clean[:8])


def normalize_product_payload(row: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in IMPORTANT_FIELDS:
        raw = _row_get(row, field)
        if field == 'preco':
            value = _money(raw)
        elif field in {'estoque', 'peso', 'largura', 'altura', 'profundidade'}:
            value = _number(raw)
        elif field == 'gtin':
            value = _gtin(raw)
        elif field == 'imagens':
            value = _images(raw)
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
    if field in {'estoque', 'peso', 'largura', 'altura', 'profundidade'}:
        return _number(site_value) == _number(bling_value)
    if field == 'gtin':
        return _gtin(site_value) == _gtin(bling_value)
    if field == 'imagens':
        return _images(site_value) == _images(bling_value)
    return _similar_text(site_value, bling_value)


def _quality_score(payload: Mapping[str, Any]) -> int:
    score = 100
    if not _identity(payload):
        score -= 35
    if not payload.get('nome'):
        score -= 20
    if not payload.get('preco'):
        score -= 12
    if not payload.get('imagens'):
        score -= 8
    if not payload.get('descricao') and not payload.get('descricao_curta'):
        score -= 10
    if not payload.get('marca'):
        score -= 5
    if not payload.get('categoria'):
        score -= 5
    return max(0, min(100, score))


def analyze_product_update_need(site_product: Mapping[str, Any] | Any, bling_product: Mapping[str, Any] | Any | None) -> ProductUpdateDecision:
    site_payload = normalize_product_payload(site_product)
    bling_payload = normalize_product_payload(bling_product or {})
    site_id = _identity(site_payload)
    bling_id = _identity(bling_payload)
    score = _quality_score(site_payload)

    if not site_id and not site_payload.get('nome'):
        return ProductUpdateDecision(
            action=ACTION_PENDING,
            should_update=False,
            should_skip=False,
            should_create=False,
            should_hold=True,
            reason='Produto do site sem SKU/código/GTIN e sem nome confiável para localizar ou cadastrar.',
            changed_fields=tuple(),
            payload=site_payload,
            quality_score=score,
            risk='alto',
            site_identity=site_id,
            bling_identity=bling_id,
        )

    if not bling_product:
        return ProductUpdateDecision(
            action=ACTION_CREATE,
            should_update=False,
            should_skip=False,
            should_create=True,
            should_hold=False,
            reason='Produto não encontrado no Bling; enviar para cadastro inteligente.',
            changed_fields=tuple(site_payload.keys()),
            payload=site_payload,
            quality_score=score,
            risk='medio' if score >= 70 else 'alto',
            site_identity=site_id,
            bling_identity=bling_id,
        )

    changed: list[str] = []
    final_payload: dict[str, Any] = {}
    for field, site_value in site_payload.items():
        if field == 'url':
            final_payload[field] = site_value
            continue
        bling_value = bling_payload.get(field, '')
        if not _same_value(field, site_value, bling_value):
            changed.append(field)
            final_payload[field] = site_value

    if not changed:
        return ProductUpdateDecision(
            action=ACTION_SKIP,
            should_update=False,
            should_skip=True,
            should_create=False,
            should_hold=False,
            reason='Produto já está atualizado no Bling; nenhuma mudança real detectada.',
            changed_fields=tuple(),
            payload={},
            quality_score=score,
            risk='baixo',
            site_identity=site_id,
            bling_identity=bling_id,
        )

    risk = 'baixo'
    if score < 60:
        risk = 'alto'
    elif any(field in changed for field in ('gtin', 'codigo', 'sku')):
        risk = 'medio'

    if risk == 'alto':
        return ProductUpdateDecision(
            action=ACTION_PENDING,
            should_update=False,
            should_skip=False,
            should_create=False,
            should_hold=True,
            reason=f'Mudanças detectadas ({", ".join(changed)}), mas a qualidade do site está baixa para atualizar automaticamente.',
            changed_fields=tuple(changed),
            payload=final_payload,
            quality_score=score,
            risk=risk,
            site_identity=site_id,
            bling_identity=bling_id,
        )

    return ProductUpdateDecision(
        action=ACTION_UPDATE,
        should_update=True,
        should_skip=False,
        should_create=False,
        should_hold=False,
        reason=f'Atualização necessária: {", ".join(changed)}.',
        changed_fields=tuple(changed),
        payload=final_payload,
        quality_score=score,
        risk=risk,
        site_identity=site_id,
        bling_identity=bling_id,
    )


__all__ = [
    'ACTION_CREATE',
    'ACTION_PENDING',
    'ACTION_SKIP',
    'ACTION_UPDATE',
    'ProductUpdateDecision',
    'analyze_product_update_need',
    'normalize_product_payload',
]
