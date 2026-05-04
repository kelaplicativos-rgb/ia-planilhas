from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import pandas as pd

from bling_app_zero.core.product_schema import PRODUCT_MASTER_COLUMNS
from bling_app_zero.rules.gtin_rules import clean_gtin
from bling_app_zero.rules.price_rules import choose_price, to_float
from bling_app_zero.rules.stock_rules import normalize_deposit, normalize_stock


ALIASES: Dict[str, Iterable[str]] = {
    "sku": ["sku", "codigo", "código", "cod", "cód", "referencia", "referência", "ref", "id"],
    "descricao": ["descricao", "descrição", "produto", "nome", "titulo", "título", "name", "title"],
    "descricao_curta": ["descricao curta", "descrição curta", "desc curta", "resumo"],
    "descricao_complementar": ["descricao complementar", "descrição complementar", "complementar", "detalhes", "observacao", "observação"],
    "gtin": ["gtin", "ean", "codigo de barras", "código de barras", "cod barras", "barcode"],
    "ncm": ["ncm"],
    "marca": ["marca", "brand", "fabricante"],
    "categoria": ["categoria", "category", "departamento", "breadcrumb"],
    "preco_custo": ["preco custo", "preço custo", "custo", "valor custo", "preco fornecedor", "preço fornecedor"],
    "preco_venda": ["preco venda", "preço venda", "preco", "preço", "valor", "price", "preco calculado", "preço calculado"],
    "estoque": ["estoque", "quantidade", "qtd", "saldo", "stock"],
    "deposito": ["deposito", "depósito", "local estoque", "almoxarifado"],
    "imagens": ["imagens", "imagem", "image", "images", "url imagem", "fotos", "foto"],
    "origem": ["origem", "source"],
    "fornecedor": ["fornecedor", "supplier"],
}


def _norm_name(value: Any) -> str:
    return str(value or "").strip().lower()


def find_column(df: pd.DataFrame, target: str) -> Optional[str]:
    aliases = list(ALIASES.get(target, [])) + [target]
    normalized = {_norm_name(col): col for col in df.columns}

    for alias in aliases:
        alias_norm = _norm_name(alias)
        if alias_norm in normalized:
            return normalized[alias_norm]

    for alias in aliases:
        alias_norm = _norm_name(alias)
        for col_norm, original in normalized.items():
            if alias_norm and alias_norm in col_norm:
                return original
    return None


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def normalize_to_product_master(
    df: pd.DataFrame,
    origem: str = "",
    fornecedor: str = "",
    deposito: str = "",
    preco_calculado_col: Optional[str] = None,
) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=PRODUCT_MASTER_COLUMNS)

    source = df.copy()
    out = pd.DataFrame(index=source.index)

    for target in PRODUCT_MASTER_COLUMNS:
        out[target] = ""

    for target in PRODUCT_MASTER_COLUMNS:
        if target in {"status_validacao", "alertas_validacao"}:
            continue
        col = find_column(source, target)
        if col is not None:
            out[target] = source[col].map(_safe_text)

    if origem:
        out["origem"] = origem
    if fornecedor:
        out["fornecedor"] = fornecedor
    if deposito:
        out["deposito"] = normalize_deposit(deposito)

    preco_origem_col = find_column(source, "preco_venda") or find_column(source, "preco_custo")
    for idx in source.index:
        preco_calculado = source.at[idx, preco_calculado_col] if preco_calculado_col and preco_calculado_col in source.columns else None
        preco_origem = source.at[idx, preco_origem_col] if preco_origem_col in source.columns else out.at[idx, "preco_venda"]
        out.at[idx, "preco_custo"] = to_float(out.at[idx, "preco_custo"], 0.0)
        out.at[idx, "preco_venda"] = choose_price(preco_calculado, preco_origem, 0.0)
        out.at[idx, "estoque"] = normalize_stock(out.at[idx, "estoque"], 0.0)
        out.at[idx, "gtin"] = clean_gtin(out.at[idx, "gtin"])
        out.at[idx, "deposito"] = normalize_deposit(out.at[idx, "deposito"])

    return out[PRODUCT_MASTER_COLUMNS].reset_index(drop=True)
