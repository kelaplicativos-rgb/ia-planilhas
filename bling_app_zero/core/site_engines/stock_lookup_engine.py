from __future__ import annotations

"""Orquestrador único para descobrir estoque real por URL de produto.

Este módulo é a porta oficial do fluxo de Atualização de estoque por site para
resolver quantidade disponível.

Regra do fluxo:
- cada URL de produto é analisada individualmente;
- primeiro tenta o HTML da própria página via stock_value_engine.py;
- se a página não trouxer quantidade real com confiança alta, tenta XML/feed do
  domínio via stock_feed_engine.py;
- fallback de disponibilidade só vem do stock_value_engine.py;
- nenhum outro módulo deve inventar quantidade de estoque.
"""

from dataclasses import dataclass

from bling_app_zero.core.site_engines.stock_feed_engine import find_stock_in_domain_feeds
from bling_app_zero.core.site_engines.stock_value_engine import extract_real_stock_value


@dataclass(frozen=True)
class StockLookupResult:
    quantity: str
    source: str
    confidence: str
    reason: str = ""
    feed_url: str = ""
    lookup_path: str = ""

    @property
    def found(self) -> bool:
        return bool(str(self.quantity or "").strip())

    @property
    def is_real_high_confidence(self) -> bool:
        return bool(self.quantity and self.confidence == "alta")


def resolve_real_stock_for_product_url(
    *,
    product_url: str,
    html: str,
    sku: str = "",
    gtin: str = "",
    name: str = "",
) -> StockLookupResult:
    """Resolve a quantidade real disponível de uma URL de produto.

    O crawler informa HTML e identificadores já coletados. Este módulo decide a
    quantidade final e registra a fonte usada.
    """
    page_result = extract_real_stock_value(html or "", page_url=product_url)

    if page_result.quantity and page_result.confidence == "alta":
        return StockLookupResult(
            quantity=page_result.quantity,
            source=page_result.source,
            confidence=page_result.confidence,
            reason=page_result.reason,
            feed_url="",
            lookup_path="pagina_alta_confianca",
        )

    feed_result = find_stock_in_domain_feeds(
        product_url,
        sku=sku,
        gtin=gtin,
        name=name,
    )
    if feed_result.quantity:
        return StockLookupResult(
            quantity=feed_result.quantity,
            source=feed_result.source,
            confidence=feed_result.confidence,
            reason=feed_result.reason,
            feed_url=feed_result.feed_url,
            lookup_path="pagina_sem_quantidade_real_depois_feed",
        )

    if page_result.quantity:
        return StockLookupResult(
            quantity=page_result.quantity,
            source=page_result.source,
            confidence=page_result.confidence,
            reason=page_result.reason,
            feed_url="",
            lookup_path="fallback_pagina_sem_feed",
        )

    return StockLookupResult(
        quantity="",
        source="nao_encontrado",
        confidence="nenhuma",
        reason="nenhum motor novo encontrou quantidade disponível para esta URL",
        feed_url="",
        lookup_path="nao_encontrado",
    )


__all__ = ["StockLookupResult", "resolve_real_stock_for_product_url"]
