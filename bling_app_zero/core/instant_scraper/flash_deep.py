from __future__ import annotations

from dataclasses import dataclass

from .browser_engine import BrowserScraperConfig, run_browser_scraper
from .flash_scan import FlashScanExtractor, FlashScanOutput
from .smart_fields import FieldRequest


@dataclass
class FlashDeepConfig:
    enabled: bool = True
    min_html_size: int = 350
    use_browser_when_available: bool = False
    min_filled_fields_before_deep: int = 2


class FlashDeepExtractor:
    """Fallback profundo do BLING INSTANT SCRAPER.

    Ajuste de performance:
    - o navegador real fica desligado por padrão, porque era o maior gargalo;
    - HTTP profundo usa timeout menor;
    - fallback só acontece quando quase nada foi capturado no modo rápido.
    """

    def __init__(self, config: FlashDeepConfig | None = None) -> None:
        self.config = config or FlashDeepConfig()
        self.fast_extractor = FlashScanExtractor(timeout=10)

    def should_deep_scan(self, fast_output: FlashScanOutput) -> bool:
        if not self.config.enabled:
            return False
        if fast_output.errors and not fast_output.html:
            return True
        if not fast_output.html:
            return True
        filled_fields = sum(1 for value in fast_output.data.values() if str(value or '').strip())
        if filled_fields >= self.config.min_filled_fields_before_deep:
            return False
        if len(fast_output.html) < self.config.min_html_size:
            return True
        if filled_fields == 0:
            return True
        return False

    def extract(self, url: str, field_requests: list[FieldRequest]) -> FlashScanOutput:
        if self.config.use_browser_when_available:
            browser_result = run_browser_scraper(
                BrowserScraperConfig(
                    operation="cadastro",
                    entry_url=url,
                    start_urls=[url],
                    model_columns=[field.original_name for field in field_requests],
                    max_pages=1,
                    max_products=12,
                    allow_entry_step=False,
                )
            )
            if not browser_result.df.empty:
                output = FlashScanOutput(url=url, used_deep=True)
                first = browser_result.df.iloc[0].to_dict()
                for field in field_requests:
                    output.data[field.kind] = first.get(field.original_name, "")
                output.errors.extend(browser_result.warnings)
                return output

        output = self.fast_extractor.extract(url, field_requests)
        output.used_deep = True
        if not output.errors:
            output.errors.append(
                "FLASH DEEP executado em modo HTTP rápido. Navegador real foi pulado para evitar lentidão."
            )
        return output
