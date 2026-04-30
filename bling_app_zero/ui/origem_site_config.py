from __future__ import annotations

from dataclasses import dataclass

from bling_app_zero.core.instant_scraper.exhaustive_engine import ExhaustiveConfig
from bling_app_zero.core.site_crawler import CrawlConfig


@dataclass(frozen=True)
class ScraperPreset:
    nome: str
    descricao: str
    max_urls: int
    max_products: int
    max_depth: int
    timeout: int
    sleep_seconds: float
    exhaustive_products: int
    exhaustive_pages: int
    browser_pages: int


PRESETS: dict[str, ScraperPreset] = {
    "Seguro": ScraperPreset(
        "Seguro",
        "Captura estável com checkpoint. Ideal para Streamlit Cloud.",
        250,
        500,
        2,
        15,
        0.12,
        1200,
        80,
        20,
    ),
    "Rápido": ScraperPreset(
        "Rápido",
        "Teste rápido para validar URL, cookie e estrutura.",
        80,
        160,
        1,
        10,
        0.05,
        300,
        30,
        8,
    ),
    "Profundo": ScraperPreset(
        "Profundo",
        "Busca maior para fornecedor completo. Usa checkpoint para não perder progresso.",
        800,
        2500,
        4,
        22,
        0.10,
        5000,
        300,
        80,
    ),
    "Sem limite prático": ScraperPreset(
        "Sem limite prático",
        "Varredura máxima. Pode demorar bastante, mas salva checkpoint durante a execução.",
        1500,
        6000,
        5,
        28,
        0.08,
        12000,
        700,
        150,
    ),
}


COLUNAS_PRIORITARIAS = [
    "Código",
    "Codigo produto *",
    "SKU",
    "Descrição",
    "Descrição Produto",
    "Descrição Curta",
    "Nome",
    "Preço unitário (OBRIGATÓRIO)",
    "Preço de Custo",
    "Preço",
    "Balanço (OBRIGATÓRIO)",
    "Estoque",
    "Deposito (OBRIGATÓRIO)",
    "Depósito",
    "GTIN",
    "GTIN **",
    "URL",
    "Imagens",
    "Imagem",
    "url_produto",
    "sku",
    "descricao",
    "nome",
    "preco",
    "estoque",
    "quantidade_real",
    "estoque_origem",
    "gtin",
    "imagem",
    "imagens",
    "agente_estrategia",
    "agente_score",
]


CHAVES_LIMPAR_SITE = [
    "df_origem",
    "df_saida",
    "origem_upload_nome",
    "origem_upload_bytes",
    "origem_upload_tipo",
    "origem_upload_ext",
    "origem_site_url",
    "origem_site_urls",
    "origem_site_total_produtos",
    "origem_site_status",
    "origem_site_ultima_busca",
    "origem_site_config",
    "origem_site_checkpoint",
    "origem_site_urls_descobertas",
    "origem_site_urls_processadas",
]


MOTOR_GOD = "BLINGGOD automático"
MOTOR_EXAUSTIVO = "Exaustivo com checkpoint"
MOTOR_RAPIDO = "Agente rápido"
MOTOR_FALLBACK = "Fallback crawler"

MOTORES_SITE = [MOTOR_GOD, MOTOR_EXAUSTIVO, MOTOR_RAPIDO, MOTOR_FALLBACK]


def config_from_preset(preset: ScraperPreset) -> CrawlConfig:
    return CrawlConfig(
        max_urls=int(preset.max_urls),
        max_products=int(preset.max_products),
        max_depth=int(preset.max_depth),
        timeout=int(preset.timeout),
        sleep_seconds=float(preset.sleep_seconds),
    )


def exhaustive_config_from_preset(preset: ScraperPreset) -> ExhaustiveConfig:
    return ExhaustiveConfig(
        max_product_urls=int(preset.exhaustive_products),
        max_base_pages=int(preset.exhaustive_pages),
        max_browser_pages=int(preset.browser_pages),
        min_score=45,
        save_every=25,
    )
