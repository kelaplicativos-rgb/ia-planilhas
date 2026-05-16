from __future__ import annotations

APP_PUBLIC_DOMAIN = 'app.mapeiaAI.com'
BRAND_NAME = 'MapeiaAI'
CREDIT_PRICE_BRL = 1.0
CREDIT_UNIT_LABEL = 'planilha mapeada'

CREDIT_PACKAGES = [
    {'label': 'Teste rápido', 'credits': 10, 'price_brl': 10.0},
    {'label': 'Operação leve', 'credits': 30, 'price_brl': 25.0},
    {'label': 'Operação recorrente', 'credits': 70, 'price_brl': 50.0},
]


def credit_price_label() -> str:
    return f'R$ {CREDIT_PRICE_BRL:.2f} por {CREDIT_UNIT_LABEL}'


__all__ = [
    'APP_PUBLIC_DOMAIN',
    'BRAND_NAME',
    'CREDIT_PACKAGES',
    'CREDIT_PRICE_BRL',
    'CREDIT_UNIT_LABEL',
    'credit_price_label',
]
