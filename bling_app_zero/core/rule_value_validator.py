from __future__ import annotations

from typing import Any

from bling_app_zero.core.text import normalize_key

EMPTY_RULE_MARKERS = {
    'vazio',
    '#vazio',
    '__vazio__',
    'em branco',
    'embranco',
    'branco',
    'limpar',
    'sem informacao',
    'seminformacao',
}


def is_empty_rule_command(value: Any) -> bool:
    return normalize_key(value) in EMPTY_RULE_MARKERS


def is_number(value: Any) -> bool:
    text = str(value if value is not None else '').strip().replace(',', '.')
    if not text:
        return False
    try:
        float(text)
        return True
    except Exception:
        return False


def rule_value_warning(target: str, value: Any) -> str:
    target_key = normalize_key(target)
    text = str(value if value is not None else '').strip()
    value_key = normalize_key(text)

    if not text or is_empty_rule_command(text):
        return ''

    if any(term in target_key for term in ('altura', 'largura', 'profundidade', 'comprimento')):
        return '' if is_number(text) else f'O valor "{text}" parece incoerente para {target}. Use número em centímetros ou VAZIO.'

    if target_key in {'itens por caixa', 'itens p caixa', 'itens p/ caixa', 'volumes'}:
        return '' if is_number(text) else f'O valor "{text}" parece incoerente para {target}. Use número ou VAZIO.'

    if target_key in {'frete gratis', 'frete grátis', 'clonar dados do pai'}:
        return '' if value_key in {'sim', 'nao', 'não', 's', 'n'} else f'O valor "{text}" parece incoerente para {target}. Use Sim, Não ou VAZIO.'

    if target_key in {'situacao', 'situação'}:
        return '' if value_key in {'ativo', 'inativo', 'excluido', 'excluído'} else f'O valor "{text}" parece incoerente para {target}. Use Ativo, Inativo ou VAZIO.'

    if target_key in {'condicao do produto', 'condição do produto'}:
        return '' if value_key in {'novo', 'usado', 'recondicionado'} else f'O valor "{text}" parece incoerente para {target}. Use Novo, Usado ou VAZIO.'

    if target_key == 'unidade':
        return f'O valor "{text}" parece incoerente para Unidade. Use algo como UN, PC, CX ou VAZIO.' if is_number(text) or len(text) > 8 else ''

    if target_key in {'unidade das medidas', 'unidade de medida', 'unidade medida'}:
        return f'O valor "{text}" parece incoerente para Unidade das medidas. Use Centímetro, Metro, Milímetro ou VAZIO.' if is_number(text) else ''

    if target_key == 'categoria':
        return f'O valor "{text}" parece incoerente para Categoria. Use nome de categoria ou VAZIO.' if is_number(text) else ''

    if target_key in {'video', 'vídeo'}:
        return '' if text.lower().startswith(('http://', 'https://')) else f'O valor "{text}" parece incoerente para Vídeo. Use URL ou VAZIO.'

    return ''


__all__ = ['EMPTY_RULE_MARKERS', 'is_empty_rule_command', 'is_number', 'rule_value_warning']
