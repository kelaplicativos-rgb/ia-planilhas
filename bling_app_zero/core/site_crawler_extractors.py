from __future__ import annotations

from bling_app_zero.core.site_crawler_extractors_fields import (
    extrair_descricao,
    extrair_marca,
    extrair_nome,
    extrair_preco,
)
from bling_app_zero.core.site_crawler_extractors_images import extrair_imagens
from bling_app_zero.core.site_crawler_extractors_main import extrair_produto_crawler

__all__ = [
    "extrair_produto_crawler",
    "extrair_nome",
    "extrair_preco",
    "extrair_descricao",
    "extrair_imagens",
    "extrair_marca",
]
