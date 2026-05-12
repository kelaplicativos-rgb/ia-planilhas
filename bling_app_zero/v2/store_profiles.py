from __future__ import annotations

from dataclasses import replace
from typing import Any

from bling_app_zero.v2.contracts import StoreProfile


def _base_profile(channel: str, store_id: str, name: str, commission: float) -> StoreProfile:
    return StoreProfile(
        store_id=str(store_id or '').strip(),
        name=name,
        channel=channel,
        operation='preco',
        required_columns=('IdProduto', 'ID na Loja', 'Preco'),
        optional_columns=('Preco Promocional', 'Nome da Loja', 'Link Externo', 'ID Fornecedor', 'ID Marca'),
        pricing_rules={
            'commission_percent': commission,
            'fixed_fee': 0.0,
            'tax_percent': 0.0,
            'profit_percent': 30.0,
            'promo_discount_percent': 0.0,
        },
        field_defaults={'ID Fornecedor': '0', 'ID Marca': '0', 'Nome da Loja': name},
    )


def mercado_livre_profile(store_id: str = '', name: str = 'Mercado Livre') -> StoreProfile:
    return _base_profile('mercado_livre', store_id, name, 16.0)


def shopee_profile(store_id: str = '', name: str = 'Shopee') -> StoreProfile:
    return _base_profile('shopee', store_id, name, 14.0)


def amazon_profile(store_id: str = '', name: str = 'Amazon') -> StoreProfile:
    return _base_profile('amazon', store_id, name, 15.0)


def generic_profile(store_id: str = '', name: str = 'Outro Marketplace') -> StoreProfile:
    return _base_profile('outro', store_id, name, 12.0)


PROFILE_BUILDERS = {
    'mercado_livre': mercado_livre_profile,
    'shopee': shopee_profile,
    'amazon': amazon_profile,
    'outro': generic_profile,
}


def build_store_profile(channel: str, store_id: str = '', name: str = '', overrides: dict[str, Any] | None = None) -> StoreProfile:
    key = str(channel or 'outro').strip().lower() or 'outro'
    builder = PROFILE_BUILDERS.get(key, generic_profile)
    profile = builder(store_id=store_id, name=name or key.replace('_', ' ').title())
    data = dict(overrides or {})
    if not data:
        return profile
    pricing_rules = {**profile.pricing_rules, **dict(data.get('pricing_rules', {}))}
    field_defaults = {**profile.field_defaults, **dict(data.get('field_defaults', {}))}
    return replace(profile, pricing_rules=pricing_rules, field_defaults=field_defaults, metadata={**profile.metadata, **data})


__all__ = ['PROFILE_BUILDERS', 'amazon_profile', 'build_store_profile', 'generic_profile', 'mercado_livre_profile', 'shopee_profile']
