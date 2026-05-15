from __future__ import annotations

EMPTY_CHOOSE_OPTION = '— escolher coluna —'
MANUAL_WRITE_OPTION = '— escrever —'
EMPTY_LEAVE_OPTION = '— deixar vazio —'
MANUAL_MAPPING_VALUE = '__BLING_MANUAL_FIXED_VALUE__'
EMPTY_MAPPING_VALUE = '__BLING_EXPLICIT_EMPTY_VALUE__'

PRICE_TARGET_ALIASES = [
    'Preço de venda',
    'Preço unitário (OBRIGATÓRIO)',
    'Preço unitário',
    'Preço',
    'Valor',
]

CADASTRO_MAPPING_CONFIRMED_KEY = 'cadastro_mapping_confirmed'
CADASTRO_MAPPING_SIGNATURE_KEY = 'cadastro_mapping_confirmed_signature'
MAPPING_PAGE_SIZE = 12
MAPPING_WIDGET_PREFIXES = (
    'cad_map_',
    'stk_map_',
    'cadastro_manual_mapping_',
    'estoque_manual_mapping_from_cadastro_',
)

__all__ = [
    'CADASTRO_MAPPING_CONFIRMED_KEY',
    'CADASTRO_MAPPING_SIGNATURE_KEY',
    'EMPTY_CHOOSE_OPTION',
    'EMPTY_LEAVE_OPTION',
    'EMPTY_MAPPING_VALUE',
    'MANUAL_MAPPING_VALUE',
    'MANUAL_WRITE_OPTION',
    'MAPPING_PAGE_SIZE',
    'MAPPING_WIDGET_PREFIXES',
    'PRICE_TARGET_ALIASES',
]
