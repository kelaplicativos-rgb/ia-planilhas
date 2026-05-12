from __future__ import annotations

from dataclasses import replace
from typing import Any

from bling_app_zero.v2.contracts import StoreProfile


def mercado_livre_profile(store_id: str = '', name: str = 'Mercado Livre') -> StoreProfile:
    return StoreProfile(
        store_id=str(store_id or '').strip(),
        name=name,
        channel='mercado_livre',
        operation='preco',
        required_columns=('IdProduto', 'ID na Loja', 'Preco'),
        optional_columns=('Preco Promocional', 'Nome da Loja', 'Link Externo', 'ID Fornecedor', 'ID Marca'),
        pricing_rules={
            'commission_percent': 16.0,
            'fixed_fee': 0.0,
            'tax_percent': 0.0,
            'profit_percent': 30.0,
            'promo_discount_percent': 0.0,
        },
        field_defaults={'ID Fornecedor': '0', 'ID Marca': '0', 'Nome da Loja': name},
    )


def shopee_profile(store_id: str = '', name: str = 'Shopee') -> StoreProfile:
    return StoreProfile(
        store_id=str(store_id or '').strip(),
        name=name,
        channel='shopee',
        operation='preco',
        required_columns=('IdProduto', 'ID na Loja', 'Preco'),
        optional_columns=('Preco Promocional', 'Nome da Loja', 'ID Fornecedor', 'ID Marca'),
        pricing_rules={
            'commission_percent': 14.0,
            'fixed_fee': 0.0,
            'tax_percent': 0.0,
            'profit_percent': 30.0,
            'promo_discount_percent': 0.0,
        },
        field_defaults={'ID Fornecedor': '0', 'ID Marca': '0', 'Nome da Loja': name},
    )


def amazon_profile(store_id: str = '', name: str = 'Amazon') -> StoreProfile:
    return StoreProfile(
        store_id=str(store_id or '').strip(),
        name=name,
        channel='amazon',
        operation='preco',
        required_columns=('IdProduto', 'ID na Loja', 'Preco'),
        optional_columns=('Preco Promocional', 'Nome da Loja', 'ID Fornecedor', 'ID Marca'),
        pricing_rules={
            'commission_percent': 15.0,
            'fixed_fee': 0.0,
            'tax_percent': 0.0,
            'profit_percent': 30.0,
            'promo_discount_percent': 0.0,
        },
        field_defaults={'ID Fornecedor': '0', 'ID Marca': '0', 'Nome da Loja': name},
    )


PROFILE_BUILDERS = {
    'mercado_livre': mercado_livre_profile,
    'shopee': shopee_profile,
    'amazon': amazon_profile,
}


def build_store_profile(channel: str, store_id: str = '', name: str = '', overrides: dict[str, Any] | None = None) -> StoreProfile:
    key = str(channel or '').strip().lower()
    builder = PROFILE_BUILDERS.get(key, mercado_livre_profile)
    profile = builder(store_id=store_id, name=name or key.replace('_', ' ').title())
    data = dict(overrides or {})
    if not data:
        return profile
    pricing_rules = {**profile.pricing_rules, **dict(data.get('pricing_rules', {}))}
    field_defaults = {**profile.field_defaults, **dict(data.get('field_defaults', {}))}
    return replace(profile, pricing_rules=pricing_rules, field_defaults=field_defaults, metadata={**profile.metadata, **data})


__all__ = ['PROFILE_BUILDERS', 'amazon_profile', 'build_store_profile', 'mercado_livre_profile', 'shopee_profile']
