from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class FieldIntent(str, Enum):
    IDENTIFICADOR = "identificador"
    NOME = "nome"
    DESCRICAO = "descricao"
    PRECO = "preco"
    ESTOQUE = "estoque"
    DEPOSITO = "deposito"
    IMAGEM = "imagem"
    GTIN = "gtin"
    CATEGORIA = "categoria"
    MARCA = "marca"
    FORNECEDOR = "fornecedor"
    NCM = "ncm"
    OUTRO = "outro"


@dataclass(frozen=True)
class RequestedField:
    column: str
    normalized: str
    intent: FieldIntent = FieldIntent.OUTRO
    required: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_column(column: object) -> FieldIntent:
    norm = normalize_text(column)
    if any(token in norm for token in ("gtin", "ean", "codigo de barras", "cod barras")):
        return FieldIntent.GTIN
    if any(token in norm for token in ("imagem", "url imagem", "foto")):
        return FieldIntent.IMAGEM
    if any(token in norm for token in ("preco", "valor", "unitario")):
        return FieldIntent.PRECO
    if any(token in norm for token in ("estoque", "quantidade", "saldo", "balanco")):
        return FieldIntent.ESTOQUE
    if any(token in norm for token in ("deposito", "local estoque")):
        return FieldIntent.DEPOSITO
    if any(token in norm for token in ("descricao", "descrição", "produto")) and "complementar" not in norm:
        return FieldIntent.NOME if "produto" in norm or "nome" in norm else FieldIntent.DESCRICAO
    if "descricao complementar" in norm or "complementar" in norm:
        return FieldIntent.DESCRICAO
    if "categoria" in norm:
        return FieldIntent.CATEGORIA
    if "marca" in norm:
        return FieldIntent.MARCA
    if "fornecedor" in norm:
        return FieldIntent.FORNECEDOR
    if "ncm" in norm:
        return FieldIntent.NCM
    if any(token in norm for token in ("sku", "codigo", "referencia", "id")):
        return FieldIntent.IDENTIFICADOR
    return FieldIntent.OUTRO


def build_requested_schema(columns: Iterable[object]) -> list[RequestedField]:
    requested: list[RequestedField] = []
    for col in columns:
        column = str(col).strip()
        if not column:
            continue
        intent = classify_column(column)
        norm = normalize_text(column)
        required = "obrigatorio" in norm or "obrigatoria" in norm or intent in {FieldIntent.NOME, FieldIntent.PRECO}
        requested.append(RequestedField(column=column, normalized=norm, intent=intent, required=required))
    return requested


def requested_intents(schema: Iterable[RequestedField]) -> set[FieldIntent]:
    return {field.intent for field in schema}
