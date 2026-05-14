from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from bling_app_zero.core.text import normalize_key


@dataclass(frozen=True)
class RequestedField:
    original: str
    key: str
    kind: str
    required: bool = False


STRICT_EMPTY_TERMS = [
    'unidade', 'ncm', 'origem', 'ipi', 'valor ipi', 'situacao', 'situação',
    'fornecedor', 'localizacao', 'localização', 'estoque maximo', 'estoque máximo',
    'estoque minimo', 'estoque mínimo', 'peso liquido', 'peso líquido', 'peso bruto',
    'largura', 'altura', 'profundidade', 'comprimento', 'data validade',
    'itens p caixa', 'itens por caixa', 'produto variacao', 'produto variação',
    'tipo producao', 'tipo produção', 'classe de enquadramento', 'lista de servicos',
    'lista de serviços', 'tipo do item', 'grupo de tags', 'tags', 'tributos',
    'codigo pai', 'código pai', 'codigo integracao', 'código integração',
    'grupo de produtos', 'cest', 'volumes', 'cross docking', 'cross-docking',
    'meses garantia', 'clonar dados do pai', 'condicao do produto', 'condição do produto',
    'frete gratis', 'frete grátis', 'numero fci', 'número fci', 'video', 'vídeo',
    'unidade de medida', 'preco de compra', 'preço de compra', 'valor base icms',
    'valor icms', 'icms proprio', 'icms próprio',
]

KIND_SYNONYMS = {
    'id_produto': ['id produto', 'identificador do produto'],
    'codigo': ['codigo produto', 'código produto', 'codigo', 'código', 'cod produto', 'sku', 'referencia', 'referência'],
    'gtin': ['gtin', 'ean', 'codigo de barras', 'código de barras', 'barcode'],
    'ficha_tecnica': ['ficha tecnica', 'ficha técnica', 'dados tecnicos', 'dados técnicos', 'informacoes tecnicas', 'informações técnicas', 'especificacoes tecnicas', 'especificações técnicas'],
    'caracteristicas': ['caracteristicas', 'características', 'detalhes do produto', 'detalhes', 'conteudo do produto', 'conteúdo do produto', 'conteudo da embalagem', 'conteúdo da embalagem', 'atributos', 'recursos', 'beneficios', 'benefícios'],
    'descricao_complementar': ['descricao complementar', 'descrição complementar', 'descricao completa', 'descrição completa', 'descricao longa', 'descrição longa', 'descricao detalhada', 'descrição detalhada', 'descricao do produto no fornecedor', 'descrição do produto no fornecedor', 'descricao do fornecedor', 'descrição do fornecedor', 'descricao rica', 'descrição rica', 'informacoes adicionais', 'informações adicionais', 'sobre o produto', 'descricao extra', 'descrição extra'],
    'descricao_curta': ['descricao curta', 'descrição curta', 'resumo do produto', 'titulo curto', 'título curto', 'nome curto'],
    'descricao': ['descricao produto', 'descrição produto', 'descricao', 'descrição', 'nome produto', 'nome do produto', 'titulo', 'título'],
    'deposito': ['deposito', 'depósito', 'almoxarifado', 'local estoque'],
    'estoque': ['balanco', 'balanço', 'estoque', 'quantidade', 'saldo', 'qtd'],
    'preco_custo': ['preco de custo', 'preço de custo', 'preco custo', 'preço custo', 'valor custo'],
    'preco_unitario': ['preco unitario', 'preço unitário', 'preco de venda', 'preço de venda', 'preco venda', 'preço venda', 'valor unitario', 'valor unitário', 'valor venda', 'preco', 'preço'],
    'observacao': ['observacao', 'observação', 'obs', 'comentario', 'comentário'],
    'data': ['data', 'dt'],
    'url': ['url', 'link', 'pagina', 'página', 'link externo'],
    'nome_apoio': ['nome apoio', 'nome auxiliar'],
    'imagem': ['imagem', 'imagens', 'url imagens', 'url imagens externas', 'foto', 'fotos'],
    'marca': ['marca', 'fabricante'],
    'categoria': ['categoria', 'categoria do produto', 'departamento'],
    'ncm': ['ncm'],
}


def _clean_column_key(column_name: str) -> str:
    key = normalize_key(column_name)
    key = key.replace(' obrigatorio', '').replace(' obrigatoria', '')
    key = key.replace('*', '').strip()
    return key


def _is_strict_empty_column(key: str) -> bool:
    return any(normalize_key(term) in key for term in STRICT_EMPTY_TERMS)


def infer_kind(column_name: str) -> str:
    key = _clean_column_key(column_name)
    if not key:
        return 'custom'
    if _is_strict_empty_column(key):
        return 'custom'

    best_kind = 'custom'
    best_score = 0
    for kind, synonyms in KIND_SYNONYMS.items():
        for synonym in synonyms:
            syn = normalize_key(synonym)
            if not syn:
                continue
            score = 0
            if key == syn:
                score = 1000 + len(syn)
            elif syn in key:
                score = 500 + len(syn)
            if score > best_score:
                best_score = score
                best_kind = kind
    return best_kind


def build_contract(columns: Iterable[str]) -> list[RequestedField]:
    result: list[RequestedField] = []
    for column in columns:
        original = str(column or '').strip()
        if not original:
            continue
        key = normalize_key(original)
        required = '*' in original or 'obrigatorio' in key or 'obrigatoria' in key
        result.append(RequestedField(original=original, key=key, kind=infer_kind(original), required=required))
    return result


def contract_from_model(df_model: pd.DataFrame | None) -> list[RequestedField]:
    if isinstance(df_model, pd.DataFrame) and len(df_model.columns):
        return build_contract([str(c) for c in df_model.columns])
    return []


def columns_from_contract(contract: list[RequestedField]) -> list[str]:
    return [field.original for field in contract]


def kinds_from_contract(contract: list[RequestedField]) -> set[str]:
    return {field.kind for field in contract}
