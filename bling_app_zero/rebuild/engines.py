from __future__ import annotations

from dataclasses import asdict
from typing import Callable, Iterable

import pandas as pd

from .model_contract import ModelContract, align_to_contract, requested_column_groups
from .operations import OperationType
from .site_extractors import ProductSnapshot, extract_product_snapshot

ProgressFn = Callable[[int, int, str], None]


def _fill_columns(row: dict[str, object], columns: Iterable[str], value: object) -> None:
    if value in (None, ""):
        return
    for col in columns:
        row[col] = value


def _snapshot_to_contract_row(snapshot: ProductSnapshot, contract: ModelContract, deposit_name: str = "") -> dict[str, object]:
    groups = requested_column_groups(contract.columns)
    data = asdict(snapshot)
    row: dict[str, object] = {col: "" for col in contract.columns}

    _fill_columns(row, groups["name"], data["name"])
    _fill_columns(row, groups["sku"], data["sku"])
    _fill_columns(row, groups["gtin"], data["gtin"])
    _fill_columns(row, groups["price"], data["price"])
    _fill_columns(row, groups["brand"], data["brand"])
    _fill_columns(row, groups["supplier"], data["supplier"] or "Não definido")
    _fill_columns(row, groups["category"], data["category"])
    _fill_columns(row, groups["images"], data["images"])
    _fill_columns(row, groups["url"], data["url"])
    _fill_columns(row, groups["ncm"], data["ncm"])

    if contract.operation == OperationType.ESTOQUE:
        _fill_columns(row, groups["stock"], data["stock"])
        _fill_columns(row, groups["deposit"], deposit_name)

    return row


class CadastroSiteEngine:
    """Motor exclusivo para cadastro por site.

    Ele não tenta gerar campos de estoque se a planilha modelo não pedir. A
    planilha modelo é o contrato: campo não solicitado fica fora ou vazio.
    """

    operation = OperationType.CADASTRO

    def run(self, urls: list[str], contract: ModelContract, progress: ProgressFn | None = None) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        total = len(urls)
        for index, url in enumerate(urls, start=1):
            if progress:
                progress(index, total, url)
            try:
                snapshot = extract_product_snapshot(url)
                rows.append(_snapshot_to_contract_row(snapshot, contract))
            except Exception:
                rows.append({col: "" for col in contract.columns} | {next(iter(contract.columns), "URL"): url})
        return align_to_contract(rows, contract)


class EstoqueSiteEngine:
    """Motor exclusivo para atualização de estoque por site.

    O foco é somente identificar o produto e preencher estoque/depósito quando
    essas colunas existem no modelo. Dados de cadastro não solicitados ficam em
    branco, sem poluir o preview nem o mapeamento.
    """

    operation = OperationType.ESTOQUE

    def run(
        self,
        urls: list[str],
        contract: ModelContract,
        deposit_name: str = "",
        progress: ProgressFn | None = None,
    ) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        total = len(urls)
        for index, url in enumerate(urls, start=1):
            if progress:
                progress(index, total, url)
            try:
                snapshot = extract_product_snapshot(url)
                rows.append(_snapshot_to_contract_row(snapshot, contract, deposit_name=deposit_name))
            except Exception:
                rows.append({col: "" for col in contract.columns} | {next(iter(contract.columns), "URL"): url})
        return align_to_contract(rows, contract)


def get_site_engine(operation: OperationType):
    return EstoqueSiteEngine() if operation == OperationType.ESTOQUE else CadastroSiteEngine()
