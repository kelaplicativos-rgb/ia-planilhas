from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

from bling_app_zero.core.site_engines.model_columns import first_existing_value, normalize_key

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "nome": ("Produto", "Nome", "Nome do produto", "Descrição", "Descricao", "Título", "Titulo", "name", "title"),
    "descricao": ("Descrição", "Descricao", "Descrição curta", "Descricao curta", "Nome", "Produto", "title", "name"),
    "descricao_complementar": ("Descrição complementar", "Descricao complementar", "Complemento", "Descrição longa", "Descricao longa", "description"),
    "preco": ("Preço", "Preco", "Preço unitário", "Preco unitario", "Preço unitário (OBRIGATÓRIO)", "Preco unitario (OBRIGATORIO)", "price", "Preço de venda", "Preco de venda"),
    "custo": ("Preço de custo", "Preco de custo", "Custo", "Valor de custo", "cost"),
    "sku": ("Código", "Codigo", "SKU", "Referência", "Referencia", "Código do produto", "Codigo do produto", "código interno", "codigo interno"),
    "gtin": ("GTIN", "EAN", "Código de barras", "Codigo de barras", "gtin", "ean", "barcode"),
    "marca": ("Marca", "Fabricante", "brand", "manufacturer"),
    "categoria": ("Categoria", "Categorias", "Categoria do produto", "category", "breadcrumb"),
    "imagens": ("URL Imagens Externas", "URL imagens externas", "Imagens", "Imagem", "image_urls", "image_url", "main_image"),
    "url": ("Link Externo", "URL", "Url", "Link", "Produto URL", "product_url", "source_url"),
    "estoque": ("Estoque", "Quantidade", "Saldo", "Balanço", "Balanco", "Qtd", "quantity", "stock"),
    "deposito": ("Depósito", "Deposito", "Nome do depósito", "Nome do deposito", "warehouse"),
    "ncm": ("NCM", "ncm"),
}


def requested_field_kind(column_name: object, operation: str = "cadastro") -> str:
    key = normalize_key(column_name)
    operation_key = normalize_key(operation)

    if any(term in key for term in ("deposito", "warehouse")):
        return "deposito"
    if any(term in key for term in ("gtin", "ean", "codigo de barras", "barcode")):
        return "gtin"
    if any(term in key for term in ("sku", "referencia", "codigo interno", "codigo produto", "codigo do produto")) or key == "codigo":
        return "sku"
    if any(term in key for term in ("quantidade", "saldo", "balanco", "estoque", "qtd")):
        return "estoque"
    if any(term in key for term in ("imagem", "imagens", "foto", "fotos", "gallery", "galeria")):
        return "imagens"
    if "url" in key or key in {"link", "link externo"}:
        return "url"
    if "descricao complementar" in key or "descricao longa" in key or key == "complemento":
        return "descricao_complementar"
    if "descricao" in key or key in {"produto", "nome", "titulo", "title", "name"}:
        return "descricao" if operation_key == "estoque" else "nome"
    if "preco" in key or "valor" in key:
        return "preco"
    if "marca" in key or "fabricante" in key:
        return "marca"
    if "categoria" in key or "breadcrumb" in key:
        return "categoria"
    if key == "ncm" or " ncm" in key:
        return "ncm"
    return ""


def requested_field_profile(requested_columns: Iterable[str], *, operation: str) -> set[str]:
    fields: set[str] = set()
    for column in requested_columns:
        kind = requested_field_kind(column, operation)
        if kind and kind != "deposito":
            fields.add(kind)
    if fields:
        fields.add("url")
    return fields


def _clean_gtin(value: object) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits if len(digits) in {8, 12, 13, 14} else ""


def resolve_value_for_column(row: pd.Series, column_name: str, *, operation: str, deposito_nome: str = "") -> str:
    kind = requested_field_kind(column_name, operation)
    if not kind:
        return ""
    if kind == "deposito":
        return str(deposito_nome or "").strip()

    value = first_existing_value(row, _FIELD_ALIASES.get(kind, (column_name,)))
    if kind == "gtin":
        return _clean_gtin(value)
    if kind == "imagens":
        return str(value or "").replace(",", "|").replace(";", "|").strip(" |")
    if kind == "estoque":
        return _normalize_stock(value)
    return str(value or "").strip()


def _normalize_stock(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if any(term in text for term in ("sem estoque", "indisponivel", "indisponível", "esgotado", "fora de estoque")):
        return "0"
    match = re.search(r"\d+(?:[\.,]\d+)?", text)
    if match:
        return match.group(0).replace(",", ".")
    if any(term in text for term in ("em estoque", "disponivel", "disponível", "comprar")):
        return "1"
    return ""


def build_model_limited_dataframe(raw_df: pd.DataFrame, requested_columns: Iterable[str], *, operation: str, deposito_nome: str = "") -> pd.DataFrame:
    requested = [str(col or "").strip() for col in requested_columns if str(col or "").strip()]
    if not isinstance(raw_df, pd.DataFrame) or raw_df.empty:
        return pd.DataFrame(columns=requested)

    rows: list[dict[str, str]] = []
    base = raw_df.copy().fillna("")
    for _, row in base.iterrows():
        item: dict[str, str] = {}
        for column in requested:
            item[column] = resolve_value_for_column(row, column, operation=operation, deposito_nome=deposito_nome)
        rows.append(item)
    return pd.DataFrame(rows, columns=requested).fillna("")
