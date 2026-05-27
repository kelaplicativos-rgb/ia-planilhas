from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Iterable

import pandas as pd

from .flash_deep import FlashDeepExtractor
from .flash_scan import FlashScanExtractor, FlashScanOutput
from .selective_extractor import align_extracted_data_to_model, operation_defaults
from .smart_fields import FieldRequest, build_field_requests


@dataclass
class FlashScraperResult:
    operation: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    raw_outputs: list[FlashScanOutput] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


class FlashScraperEngine:
    """Orquestrador isolado do motor BLINGFLASH.

    Fluxo ajustado para busca por site:
    - tenta primeiro o HTTP rápido;
    - só usa fallback profundo quando a página realmente não trouxe dados úteis;
    - processa múltiplas URLs em paralelo, mantendo a ordem original no resultado.
    """

    def __init__(self, max_workers: int = 6) -> None:
        self.max_workers = max(1, int(max_workers or 1))

    def _extract_one(self, url: str, field_requests: list[FieldRequest]) -> FlashScanOutput:
        fast = FlashScanExtractor()
        deep = FlashDeepExtractor()
        output = fast.extract(url, field_requests)
        if deep.should_deep_scan(output):
            output = deep.extract(url, field_requests)
        return output

    def run(
        self,
        urls: Iterable[str],
        model_columns: Iterable[object] | pd.DataFrame | None,
        *,
        operation: str = "cadastro",
    ) -> FlashScraperResult:
        urls_clean = list(dict.fromkeys(str(url or "").strip() for url in urls if str(url or "").strip()))
        defaults = operation_defaults(operation)
        field_requests = build_field_requests(model_columns)

        result = FlashScraperResult(operation=defaults["mode"])

        if not urls_clean:
            result.errors.append("Nenhuma URL informada para o BLINGFLASH.")
            return result
        if not field_requests:
            result.errors.append("Nenhuma coluna de modelo informada para extração seletiva.")
            return result

        workers = min(self.max_workers, len(urls_clean))
        ordered_outputs: list[FlashScanOutput | None] = [None] * len(urls_clean)

        if workers <= 1:
            for index, url in enumerate(urls_clean):
                ordered_outputs[index] = self._extract_one(url, field_requests)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(self._extract_one, url, field_requests): index for index, url in enumerate(urls_clean)}
                for future in as_completed(futures):
                    index = futures[future]
                    url = urls_clean[index]
                    try:
                        ordered_outputs[index] = future.result()
                    except Exception as exc:  # proteção para não travar o lote inteiro
                        ordered_outputs[index] = FlashScanOutput(url=url, errors=[f"Falha ao extrair URL em paralelo: {exc}"])

        for output in ordered_outputs:
            if output is None:
                continue
            result.raw_outputs.append(output)
            result.errors.extend(output.errors)
            result.rows.append(
                align_extracted_data_to_model(
                    output.data,
                    field_requests,
                    include_support_name=bool(defaults["include_support_name"]),
                )
            )

        return result


def run_flash_scraper(
    urls: Iterable[str],
    model_columns: Iterable[object] | pd.DataFrame | None,
    *,
    operation: str = "cadastro",
) -> FlashScraperResult:
    return FlashScraperEngine().run(urls, model_columns, operation=operation)
