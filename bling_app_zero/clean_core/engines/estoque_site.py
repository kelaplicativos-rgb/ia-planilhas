from __future__ import annotations

from typing import Any

import pandas as pd

from ..operations import Operation
from ..schema import FieldIntent, RequestedField
from .base import EngineResult
from .mapper import apply_payload_to_model, blank_payload
from .site_tools import extract_stock, extract_title, fetch_url, should_extract


class EstoqueSiteEngine:
    operation = Operation.ESTOQUE
    name = "Motor independente: estoque por site"

    def run(self, *, model_df: pd.DataFrame, requested_schema: list[RequestedField], urls: list[str], deposit_name: str = "") -> EngineResult:
        payloads: list[dict[FieldIntent, Any]] = []
        logs: list[str] = []
        warnings: list[str] = []

        clean_urls = [url.strip() for url in urls if str(url or "").strip()]
        if not clean_urls:
            return EngineResult(dataframe=apply_payload_to_model(model_df, requested_schema, [blank_payload(requested_schema)]), warnings=["Nenhum link informado."])

        for url in clean_urls:
            snapshot = fetch_url(url)
            payload = blank_payload(requested_schema)
            payload[FieldIntent.IDENTIFICADOR] = snapshot.url or url

            if not snapshot.ok:
                warnings.append(f"Falha ao acessar {url}: {snapshot.error}")
                payloads.append(payload)
                continue

            if should_extract(FieldIntent.NOME, requested_schema) or should_extract(FieldIntent.DESCRICAO, requested_schema):
                title = extract_title(snapshot)
                payload[FieldIntent.NOME] = title
                payload[FieldIntent.DESCRICAO] = title

            if should_extract(FieldIntent.ESTOQUE, requested_schema):
                payload[FieldIntent.ESTOQUE] = extract_stock(snapshot)

            if should_extract(FieldIntent.DEPOSITO, requested_schema):
                payload[FieldIntent.DEPOSITO] = deposit_name

            payloads.append(payload)
            logs.append(f"Estoque: capturado somente estoque/identificação solicitados pelo modelo em {snapshot.url}")

        dataframe = apply_payload_to_model(model_df, requested_schema, payloads)
        return EngineResult(dataframe=dataframe, logs=logs, warnings=warnings)
