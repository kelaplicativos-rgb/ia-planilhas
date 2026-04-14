from __future__ import annotations

from copy import deepcopy
from typing import Any

from .fornecedores_adaptativos_detectores import analisar_fornecedor_por_html
from .fornecedores_adaptativos_storage import (
    atualizar_fornecedor,
    carregar_fornecedor,
    extrair_dominio,
    listar_fornecedores,
    salvar_fornecedor,
)

# ==========================================================
# PRESETS DE FORNECEDORES
# ==========================================================


def _deep_merge_dict(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """
    Merge profundo simples, preservando compatibilidade com a base atual.
    Valores de `extra` sobrescrevem os de `base`.
    """
    resultado: dict[str, Any] = deepcopy(base)

    for chave, valor in (extra or {}).items():
        if isinstance(valor, dict) and isinstance(resultado.get(chave), dict):
            resultado[chave] = _deep_merge_dict(resultado[chave], valor)
        else:
            resultado[chave] = deepcopy(valor)

    return resultado


def _normalizar_dominio_fornecedor(dominio_ou_url: str) -> str:
    return extrair_dominio(dominio_ou_url)


def _preset_obaobamix(dominio: str) -> dict[str, Any]:
    """
    Preset do fornecedor Oba Oba Mix.

    Baseado no comportamento observado no painel autenticado:
    - rota /admin/products
    - endpoint DataTables autenticado retornando JSON paginado
    - campos com HTML embutido em sku/name/price/inventory/photo
    """
    return {
        "dominio": dominio,
        "tipo": "api_datatables_auth",
        "confianca": 0.99,
        "origem": "preset_api_auth",
        "imagens_multiplas": True,
        "principal": True,
        "seletores": {
            # JSON paths semânticos para orientar o restante do pipeline.
            "codigo": ["data[].sku"],
            "nome": ["data[].name"],
            "modelo": ["data[].model"],
            "gtin": ["data[].ean"],
            "preco": ["data[].price", "data[].price_of"],
            "estoque": ["data[].inventory"],
            "imagem": ["data[].photo"],
            "marca": ["data[].brand.name", "data[].brand_name"],
            "cor": ["data[].color.name"],
            "id_externo": ["data[].id"],
        },
        "links": {
            "painel": ["/admin/products"],
            "api_produtos": ["/admin/products"],
            "api_modo": ["datatables_server_side"],
            "api_paginacao": ["start_length"],
            "api_parametros_base": [
                "draw",
                "start",
                "length",
                "search[value]",
                "order[0][column]",
                "order[0][dir]",
                "columns[*][data]",
            ],
            "api_campo_lista": ["data"],
            "api_campo_total": ["recordsTotal"],
            "api_campo_filtrado": ["recordsFiltered"],
            "detalhe_visualizacao": ["#viewProduct", "btnViewProduct"],
        },
    }


def _preset_por_dominio(dominio: str) -> dict[str, Any]:
    dominio = _normalizar_dominio_fornecedor(dominio)
    if not dominio:
        return {}

    if dominio in {
        "app.obaobamix.com.br",
        "obaobamix.com.br",
    }:
        return _preset_obaobamix(dominio)

    return {}


def _deve_promover_preset(
    existente: dict[str, Any],
    preset: dict[str, Any],
) -> bool:
    if not preset:
        return False

    if not existente:
        return True

    tipo_existente = str(existente.get("tipo", "") or "").strip().lower()
    origem_existente = str(existente.get("origem", "") or "").strip().lower()
    confianca_existente = float(existente.get("confianca", 0.0) or 0.0)
    confianca_preset = float(preset.get("confianca", 0.0) or 0.0)

    if tipo_existente in {"", "generico", "woocommerce", "shopify", "vtex"}:
        return True

    if origem_existente in {"", "ia_adaptativa"}:
        return True

    if confianca_preset > confianca_existente:
        return True

    links_existentes = existente.get("links", {}) or {}
    if not isinstance(links_existentes, dict):
        links_existentes = {}

    if not links_existentes.get("api_produtos"):
        return True

    return False


def obter_fornecedor_preset(url_ou_dominio: str) -> dict[str, Any]:
    dominio = _normalizar_dominio_fornecedor(url_ou_dominio)
    return _preset_por_dominio(dominio)


# ==========================================================
# FLUXO PRINCIPAL
# ==========================================================


def garantir_fornecedor_adaptativo(url: str, html: str) -> dict[str, Any]:
    dominio = extrair_dominio(url)
    if not dominio:
        return {}

    existente = carregar_fornecedor(dominio)
    preset = obter_fornecedor_preset(dominio)

    # 1) Se houver preset melhor que o existente, promove o preset.
    if _deve_promover_preset(existente, preset):
        config_final = _deep_merge_dict(existente or {}, preset)
        salvar_fornecedor(dominio, config_final, sobrescrever=True)
        return carregar_fornecedor(dominio) or config_final

    # 2) Se já houver configuração salva válida, usa ela.
    if existente:
        return existente

    # 3) Se não há configuração salva, mas há preset conhecido, salva preset.
    if preset:
        salvar_fornecedor(dominio, preset, sobrescrever=True)
        return carregar_fornecedor(dominio) or preset

    # 4) Fallback padrão: heurística por HTML.
    config = analisar_fornecedor_por_html(url, html)
    salvar_fornecedor(dominio, config, sobrescrever=False)
    return carregar_fornecedor(dominio) or config


def promover_fornecedor_preset(url_ou_dominio: str) -> dict[str, Any]:
    """
    Força a promoção do preset conhecido do domínio, quando existir.
    Útil para migração manual de fornecedores já aprendidos como genéricos.
    """
    dominio = extrair_dominio(url_ou_dominio)
    if not dominio:
        return {}

    preset = obter_fornecedor_preset(dominio)
    if not preset:
        return carregar_fornecedor(dominio)

    existente = carregar_fornecedor(dominio)
    config_final = _deep_merge_dict(existente or {}, preset)
    salvar_fornecedor(dominio, config_final, sobrescrever=True)
    return carregar_fornecedor(dominio) or config_final


def aplicar_patch_fornecedor_com_preset(
    url_ou_dominio: str,
    patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Aplica patch em fornecedor existente sem perder o preset do domínio.
    """
    dominio = extrair_dominio(url_ou_dominio)
    if not dominio:
        return {}

    atual = carregar_fornecedor(dominio) or {}
    preset = obter_fornecedor_preset(dominio) or {}
    patch = patch or {}

    config_final = _deep_merge_dict(preset, atual)
    config_final = _deep_merge_dict(config_final, patch)

    salvar_fornecedor(dominio, config_final, sobrescrever=True)
    return carregar_fornecedor(dominio) or config_final


__all__ = [
    "extrair_dominio",
    "carregar_fornecedor",
    "listar_fornecedores",
    "salvar_fornecedor",
    "atualizar_fornecedor",
    "analisar_fornecedor_por_html",
    "garantir_fornecedor_adaptativo",
    "obter_fornecedor_preset",
    "promover_fornecedor_preset",
    "aplicar_patch_fornecedor_com_preset",
]
