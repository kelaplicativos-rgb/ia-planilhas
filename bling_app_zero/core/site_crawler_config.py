
from __future__ import annotations

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

FORNECEDORES_DEDICADOS = {
    "megacentereletronicos.com.br": {
        "produto_hints": [
            "/produto",
            "/product",
            "/p/",
            "/item/",
            "/sku/",
            "/loja/produto/",
        ],
        "categoria_hints": [
            "/categoria",
            "/categorias",
            "/collections/",
            "/colecao/",
            "/departamento/",
            "/busca",
            "/search",
            "/catalogo",
        ],
        "title_selectors": [
            "h1",
            ".product_title",
            ".product-name",
            ".entry-title",
            "[class*='product-title']",
            "[itemprop='name']",
            "meta[property='og:title']",
        ],
        "price_selectors": [
            ".price",
            ".product-price",
            "[class*='price']",
            "[itemprop='price']",
            "[data-price]",
            "meta[property='product:price:amount']",
        ],
        "image_selectors": [
            "meta[property='og:image']",
            "img[src]",
            "img[data-src]",
            "img[data-lazy-src]",
            ".product-gallery img[src]",
            ".woocommerce-product-gallery img[src]",
        ],
    },
    "atacadum.com.br": {
        "produto_hints": [
            "/produto",
            "/product",
            "/p/",
            "/item/",
            "/sku/",
            "/iphone",
            "/xiaomi",
            "/realme",
        ],
        "categoria_hints": [
            "/categoria",
            "/categorias",
            "/collections/",
            "/colecao/",
            "/departamento/",
            "/busca",
            "/search",
            "/celulares-smartphone",
        ],
        "title_selectors": [
            "h1",
            ".product_title",
            ".product-name",
            ".entry-title",
            "[class*='product-title']",
            "[itemprop='name']",
            "meta[property='og:title']",
        ],
        "price_selectors": [
            ".price",
            ".product-price",
            "[class*='price']",
            "[itemprop='price']",
            "[data-price]",
            "meta[property='product:price:amount']",
        ],
        "image_selectors": [
            "meta[property='og:image']",
            "img[src]",
            "img[data-src]",
            "img[data-lazy-src]",
            ".product-gallery img[src]",
            ".woocommerce-product-gallery img[src]",
        ],
    },
}

STOP_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".bmp",
    ".ico",
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".mp4",
    ".mp3",
    ".avi",
    ".mov",
    ".css",
    ".js",
    ".xml",
    ".json",
)

ROTAS_INICIAIS_PADRAO = (
    "/",
    "/produtos",
    "/produto",
    "/categorias",
    "/categoria",
    "/departamentos",
    "/collections",
    "/colecoes",
    "/shop",
    "/loja",
    "/busca",
    "/search",
    "/catalogo",
    "/catalog",
)

STOP_URL_HINTS = (
    "/conta",
    "/account",
    "/login",
    "/cadastro",
    "/register",
    "/carrinho",
    "/cart",
    "/checkout",
    "/politica",
    "/privacy",
    "/privacidade",
    "/termos",
    "/terms",
    "/suporte",
    "/support",
    "/blog",
    "/noticia",
    "/news",
    "/faq",
    "/ajuda",
    "/help",
    "/sobre",
    "/about",
    "/quem-somos",
    "/contato",
    "/contact",
)

STOP_TITLE_EXATO = {
    "todos os produtos",
    "produtos",
    "loja",
    "home",
    "início",
    "inicio",
}

STOP_DESC_HINTS = (
    "loja física e online",
    "loja fisica e online",
    "assistência técnica",
    "assistencia tecnica",
    "atendimento online e presencial",
    "horário:",
    "horario:",
)

STOP_IMAGE_HINTS = (
    "facebook.com/tr",
    "placeholder",
    "logo",
    "favicon",
    "icon",
    ".svg",
    "noscript=1",
)
