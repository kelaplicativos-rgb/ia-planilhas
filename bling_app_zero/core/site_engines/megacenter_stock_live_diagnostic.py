from __future__ import annotations

"""Diagnóstico live do motor de estoque usando Mega Center.

Este arquivo não altera o fluxo principal. Ele serve para executar uma simulação
controlada com o link real do fornecedor quando o app/ambiente tiver internet.

Uso esperado em ambiente com rede:

    python -m bling_app_zero.core.site_engines.megacenter_stock_live_diagnostic

O diagnóstico valida:
- descoberta de links de produto a partir de https://megacentereletronicos.com.br;
- extração enxuta do motor de estoque;
- acionamento do stock_value_engine;
- acionamento do stock_feed_engine quando a página não trouxer quantidade real;
- colunas finais úteis para atualizar estoque.
"""

import json
from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd

from bling_app_zero.core.product_url_discovery_infinity import discover_product_urls_infinity
from bling_app_zero.core.site_engines.estoque_fast_crawler import crawl_estoque_fast_dataframe
from bling_app_zero.core.site_engines.stock_feed_engine import candidate_feed_urls

MEGA_CENTER_URL = "https://megacentereletronicos.com.br"
DEFAULT_REQUESTED_FIELDS = {"descricao", "sku", "gtin", "estoque"}


@dataclass(frozen=True)
class MegaCenterStockDiagnosticResult:
    seed_url: str
    requested_fields: list[str]
    discovered_products: int
    sampled_products: list[str]
    candidate_feeds: list[str]
    rows: int
    columns: list[str]
    estoque_values: list[str]
    fonte_estoque_values: list[str]
    confianca_estoque_values: list[str]
    preview: list[dict[str, str]]


def _safe_unique(values: Iterable[object], limit: int = 20) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
        if len(output) >= limit:
            break
    return output


def run_megacenter_stock_live_diagnostic(
    *,
    seed_url: str = MEGA_CENTER_URL,
    max_products: int = 10,
    max_workers: int = 6,
    requested_fields: Iterable[str] = DEFAULT_REQUESTED_FIELDS,
) -> MegaCenterStockDiagnosticResult:
    fields = {str(field or "").strip().lower() for field in requested_fields if str(field or "").strip()}
    product_urls = discover_product_urls_infinity([seed_url], max_products=max_products)

    df = crawl_estoque_fast_dataframe(
        [seed_url],
        requested_fields=fields,
        max_products=max_products,
        max_workers=max_workers,
    )
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()

    preview_df = df.fillna("").head(10)
    preview = [
        {str(key): str(value) for key, value in row.items()}
        for row in preview_df.to_dict(orient="records")
    ]

    return MegaCenterStockDiagnosticResult(
        seed_url=seed_url,
        requested_fields=sorted(fields),
        discovered_products=len(product_urls),
        sampled_products=product_urls[:10],
        candidate_feeds=candidate_feed_urls(seed_url),
        rows=len(df),
        columns=[str(col) for col in df.columns],
        estoque_values=_safe_unique(df.get("Estoque", [])) if not df.empty else [],
        fonte_estoque_values=_safe_unique(df.get("Fonte estoque", [])) if not df.empty else [],
        confianca_estoque_values=_safe_unique(df.get("Confianca estoque", [])) if not df.empty else [],
        preview=preview,
    )


def main() -> None:
    result = run_megacenter_stock_live_diagnostic()
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
