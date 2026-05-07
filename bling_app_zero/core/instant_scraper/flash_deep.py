from __future__ import annotations

from dataclasses import dataclass

from .flash_scan import FlashScanExtractor, FlashScanOutput
from .smart_fields import FieldRequest


@dataclass
class FlashDeepConfig:
    enabled: bool = True
    min_html_size: int = 800


class FlashDeepExtractor:
    """Fallback seguro para páginas difíceis.

    Nesta primeira implantação ele não liga navegador pesado por padrão. A classe
    já isola o ponto onde Playwright/JS rendering deve entrar depois, sem
    contaminar o motor de cadastro nem o motor de estoque.
    """

    def __init__(self, config: FlashDeepConfig | None = None) -> None:
        self.config = config or FlashDeepConfig()
        self.fast_extractor = FlashScanExtractor(timeout=28)

    def should_deep_scan(self, fast_output: FlashScanOutput) -> bool:
        if not self.config.enabled:
            return False
        if fast_output.errors:
            return True
        if not fast_output.html or len(fast_output.html) < self.config.min_html_size:
            return True
        if not any(value for value in fast_output.data.values()):
            return True
        return False

    def extract(self, url: str, field_requests: list[FieldRequest]) -> FlashScanOutput:
        output = self.fast_extractor.extract(url, field_requests)
        output.used_deep = True
        if not output.errors:
            output.errors.append(
                "FLASH DEEP preparado: fallback executado em modo seguro sem navegador pesado."
            )
        return output
