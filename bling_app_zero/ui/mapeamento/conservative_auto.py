from __future__ import annotations

"""Regras conservadoras para mapeamento automático de colunas.

Princípio do usuário:
    Se não for 100% verdadeiro, NÃO mapear automaticamente.
    Deixar em branco para o usuário fazer manualmente.

Este módulo não tenta ser "esperto" demais. Ele só aprova correspondências
quando há alta segurança semântica e textual. Relações fracas, parecidas ou
ambíguas são rejeitadas.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, Optional


EMPTY_OPTIONS = {"", "—", "--", "nenhum", "nenhuma", "não mapear", "nao mapear", "manual"}

# Sinônimos extremamente seguros. Evitar colocar termos genéricos demais aqui.
# A chave é o destino Bling normalizado; os valores são possíveis origens seguras.
STRICT_SYNONYMS: dict[str, set[str]] = {
    "codigo": {"codigo", "cod", "sku", "referencia", "ref"},
    "sku": {"sku", "codigo", "cod", "referencia", "ref"},
    "gtin": {"gtin", "ean", "codigo de barras", "cod barras", "barcode"},
    "ean": {"ean", "gtin", "codigo de barras", "cod barras", "barcode"},
    "preco": {"preco", "valor", "preco venda", "valor venda"},
    "preco unitario obrigatorio": {"preco", "valor", "preco venda", "valor venda", "preco unitario"},
    "descricao": {"descricao", "nome", "produto", "titulo", "descricao produto"},
    "nome": {"nome", "produto", "titulo", "descricao"},
    "marca": {"marca", "brand", "fabricante"},
    "categoria": {"categoria", "category", "departamento"},
    "estoque": {"estoque", "quantidade", "qtd", "saldo"},
    "quantidade": {"quantidade", "qtd", "estoque", "saldo"},
    "deposito": {"deposito", "almoxarifado"},
    "ncm": {"ncm"},
    "cest": {"cest"},
    "unidade": {"unidade", "un", "und"},
    "peso": {"peso", "peso bruto", "peso liquido"},
    "altura": {"altura"},
    "largura": {"largura"},
    "profundidade": {"profundidade", "comprimento"},
    "imagens": {"imagens", "imagem", "url imagem", "urls imagens", "fotos", "foto"},
    "url imagens": {"imagens", "imagem", "url imagem", "urls imagens", "fotos", "foto"},
}

# Termos que frequentemente geram mapeamento errado e só devem passar por match literal.
DANGEROUS_GENERIC_TERMS = {
    "descricao curta",
    "descricao complementar",
    "descricao detalhada",
    "observacao",
    "observacoes",
    "video",
    "url video",
    "url",
    "link",
    "texto",
    "complemento",
    "complementar",
}


def normalize_column_name(value: object) -> str:
    """Normaliza nome de coluna para comparação conservadora."""
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Remove ruídos comuns do modelo Bling sem perder o significado.
    text = text.replace("obrigatorio", "").strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_empty_mapping(value: object) -> bool:
    return normalize_column_name(value) in EMPTY_OPTIONS


def _tokens(text: str) -> set[str]:
    return {token for token in text.split() if token}


def _is_dangerous_generic(source_norm: str, target_norm: str) -> bool:
    joined = {source_norm, target_norm}
    return any(term in joined for term in DANGEROUS_GENERIC_TERMS)


def is_safe_auto_mapping(source_column: object, target_column: object) -> bool:
    """Retorna True somente quando o mapeamento automático é seguro.

    Regras:
    1. Igualdade normalizada: aprovado.
    2. Sinônimo estrito aprovado: aprovado.
    3. Texto quase idêntico, com tokens compatíveis e ratio >= 0.98: aprovado.
    4. Qualquer caso ambíguo/genérico/perigoso: reprovado.
    """
    source_norm = normalize_column_name(source_column)
    target_norm = normalize_column_name(target_column)

    if not source_norm or not target_norm:
        return False

    if source_norm in EMPTY_OPTIONS or target_norm in EMPTY_OPTIONS:
        return False

    if source_norm == target_norm:
        return True

    # Campos perigosos só passam se forem literalmente iguais após normalização.
    if _is_dangerous_generic(source_norm, target_norm):
        return False

    if source_norm in STRICT_SYNONYMS.get(target_norm, set()):
        return True

    if target_norm in STRICT_SYNONYMS.get(source_norm, set()):
        return True

    source_tokens = _tokens(source_norm)
    target_tokens = _tokens(target_norm)

    if not source_tokens or not target_tokens:
        return False

    # Evita relação fraca: "descricao curta" -> "descricao complementar", etc.
    if source_tokens != target_tokens:
        return False

    ratio = SequenceMatcher(None, source_norm, target_norm).ratio()
    return ratio >= 0.98


def choose_safe_source(target_column: object, source_columns: Iterable[object]) -> Optional[str]:
    """Escolhe uma coluna de origem segura para um destino; senão retorna None."""
    safe_matches: list[str] = []

    for source in source_columns:
        if is_safe_auto_mapping(source, target_column):
            safe_matches.append(str(source))

    # Se houver mais de uma possível, é ambíguo: não mapear.
    if len(safe_matches) == 1:
        return safe_matches[0]

    return None


def sanitize_auto_mapping(mapping: dict[object, object], source_columns: Iterable[object]) -> dict[object, str]:
    """Limpa mapeamentos automáticos inseguros.

    Esperado: dict[target_column] = source_column.
    Retorno: dict[target_column] = source_column seguro ou "".
    """
    source_set = {str(col) for col in source_columns}
    cleaned: dict[object, str] = {}

    for target, source in mapping.items():
        source_text = "" if source is None else str(source)

        if not source_text or source_text not in source_set:
            cleaned[target] = ""
            continue

        cleaned[target] = source_text if is_safe_auto_mapping(source_text, target) else ""

    return cleaned


def build_conservative_auto_mapping(target_columns: Iterable[object], source_columns: Iterable[object]) -> dict[str, str]:
    """Cria mapeamento automático ultra-conservador.

    Só preenche quando existe exatamente uma origem segura para o destino.
    """
    sources = list(source_columns)
    result: dict[str, str] = {}

    for target in target_columns:
        target_text = str(target)
        result[target_text] = choose_safe_source(target_text, sources) or ""

    return result
