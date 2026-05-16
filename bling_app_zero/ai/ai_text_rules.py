from __future__ import annotations

import re

MAX_TITLE_LENGTH = 59
TITLE_TARGET_COLUMNS = {
    'nome', 'nome produto', 'produto', 'titulo', 'título', 'descricao', 'descrição', 'name', 'title', 'nome*'
}
DESCRIPTION_TARGET_TERMS = {
    'descricao complementar', 'descrição complementar', 'descricao completa', 'descrição completa', 'descricao longa', 'descrição longa', 'description'
}


def clean_title_to_limit(value: object, limit: int = MAX_TITLE_LENGTH) -> str:
    text = re.sub(r'\s+', ' ', str(value or '').strip())
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0].rstrip()
    return cut[:limit].rstrip()


def is_title_column(column_name: object) -> bool:
    key = re.sub(r'[^a-z0-9*]+', ' ', str(column_name or '').strip().lower()).strip()
    return key in TITLE_TARGET_COLUMNS or any(term in key for term in ['nome produto', 'titulo', 'título'])


def is_description_column(column_name: object) -> bool:
    key = re.sub(r'[^a-z0-9]+', ' ', str(column_name or '').strip().lower()).strip()
    return key in DESCRIPTION_TARGET_TERMS or any(term in key for term in ['descricao complementar', 'descrição complementar', 'descricao completa', 'descrição completa'])


def ai_text_rules_prompt() -> str:
    return (
        'Regras obrigatórias de texto comercial do MapeiaAI: '
        '1) títulos/nomes de produto devem ter no máximo 59 caracteres; '
        '2) não invente especificações como cor, voltagem, tamanho, compatibilidade ou marca; '
        '3) corrija ortografia e capitalização; '
        '4) descrições complementares devem ser persuasivas, claras e úteis para compra, mantendo fidelidade aos dados reais; '
        '5) nunca altere preço, estoque, GTIN/EAN, SKU, ID, URL, imagem ou campos fiscais sem solicitação explícita.'
    )


__all__ = [
    'MAX_TITLE_LENGTH',
    'ai_text_rules_prompt',
    'clean_title_to_limit',
    'is_description_column',
    'is_title_column',
]
