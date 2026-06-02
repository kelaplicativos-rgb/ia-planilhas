from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class SitePlatformSignal:
    platform: str
    confidence: float
    reason: str


def detect_site_platform(raw_urls: str) -> SitePlatformSignal:
    text = str(raw_urls or '').lower()
    host = ''
    for token in text.replace('\n', ' ').replace(',', ' ').split():
        if token.startswith(('http://', 'https://')):
            host = urlparse(token).netloc.lower().replace('www.', '')
            break

    checks = [
        ('stoqui', ['stoqui.shop', 'stoqui', '/api/', 'product_id'], 0.92),
        ('mega_center', ['megacentereletronicos.com.br', 'mega-center-eletronicos'], 0.90),
        ('shopify', ['myshopify.com', '/products/', 'cdn.shopify.com'], 0.88),
        ('woocommerce', ['wp-content', 'woocommerce', '?add-to-cart='], 0.84),
        ('loja_integrada', ['lojaintegrada', 'cdn.awsli.com.br'], 0.84),
        ('nuvemshop', ['nuvemshop', 'tiendanube', '/produtos/'], 0.82),
        ('tray', ['tray', 'traycheckout', '/loja/'], 0.78),
    ]
    for platform, hints, confidence in checks:
        if any(hint in text or hint in host for hint in hints):
            return SitePlatformSignal(platform=platform, confidence=confidence, reason=f'Detectado por sinais de URL/HTML: {platform}.')

    if host:
        return SitePlatformSignal(platform='generico', confidence=0.50, reason=f'Plataforma não identificada automaticamente para {host}.')
    return SitePlatformSignal(platform='desconhecido', confidence=0.20, reason='Nenhuma URL válida informada para detecção de plataforma.')


__all__ = ['SitePlatformSignal', 'detect_site_platform']
