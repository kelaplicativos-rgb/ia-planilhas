from __future__ import annotations

from bling_app_zero.core.site_crawler_helpers_links import (
    extrair_links_paginacao_crawler,
    extrair_links_produtos_crawler,
    link_parece_produto_crawler,
)
from bling_app_zero.core.site_crawler_helpers_meta import (
    meta_content_crawler,
    primeiro_texto_crawler,
    todas_imagens_crawler,
)
from bling_app_zero.core.site_crawler_helpers_stock import (
    detectar_estoque_crawler,
)
from bling_app_zero.core.site_crawler_helpers_text import (
    MAX_PAGINAS,
    MAX_PRODUTOS,
    MAX_THREADS,
    HELPERS_VERSION,
    normalizar_url_crawler,
    numero_texto_crawler,
    texto_limpo_crawler,
    url_mesmo_dominio_crawler,
)
from bling_app_zero.core.site_crawler_helpers_jsonld import (
    buscar_produto_jsonld_crawler,
    extrair_json_ld_crawler,
)

__all__ = [
    "HELPERS_VERSION",
    "MAX_THREADS",
    "MAX_PAGINAS",
    "MAX_PRODUTOS",
    "normalizar_url_crawler",
    "url_mesmo_dominio_crawler",
    "texto_limpo_crawler",
    "numero_texto_crawler",
    "extrair_json_ld_crawler",
    "buscar_produto_jsonld_crawler",
    "meta_content_crawler",
    "primeiro_texto_crawler",
    "todas_imagens_crawler",
    "detectar_estoque_crawler",
    "link_parece_produto_crawler",
    "extrair_links_produtos_crawler",
    "extrair_links_paginacao_crawler",
]
