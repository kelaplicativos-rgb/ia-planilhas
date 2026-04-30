from __future__ import annotations

from dataclasses import dataclass


BLOCKED_URL_PARTS = [
    "carrinho",
    "cart",
    "checkout",
    "login",
    "minha-conta",
    "account",
    "wishlist",
    "favoritos",
    "javascript:",
    "mailto:",
    "tel:",
    "politica",
    "privacidade",
    "termos",
]


PRODUCT_HINTS = [
    "/produto",
    "/product",
    "/p/",
    "produto/",
]


CATEGORY_HINTS = [
    "/categoria",
    "/category",
    "/departamento",
    "/colecao",
    "/collections",
]


@dataclass
class CrawlConfig:
    max_urls: int = 250
    max_products: int = 300
    max_depth: int = 2
    timeout: int = 15
    sleep_seconds: float = 0.15
    max_seconds: int = 180
    max_queue_size: int = 1500
