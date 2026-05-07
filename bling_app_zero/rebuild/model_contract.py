from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

import pandas as pd

from .operations import OperationType, looks_like_stock_model, normalize_operation


@dataclass(frozen=True)
class ModelContract:
    operation: OperationType
    columns: tuple[str, ...]
    source_filename: str

    @property
    def empty_frame(self) -> pd.DataFrame:
        return pd.DataFrame(columns=list(self.columns))


def _dedupe_columns(columns: Iterable[object]) -> list[str]:
    seen: dict[str, int] = {}
    final: list[str] = []
    for col in columns:
        name = str(col).strip()
        if not name or name.lower().startswith("unnamed"):
            continue
        count = seen.get(name, 0)
        seen[name] = count + 1
        final.append(name if count == 0 else f"{name} ({count + 1})")
    return final


def read_uploaded_model(uploaded_file, selected_operation: str | None = None) -> tuple[ModelContract, pd.DataFrame]:
    filename = getattr(uploaded_file, "name", "modelo")
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    raw = uploaded_file.getvalue()
    buffer = BytesIO(raw)

    if suffix == "csv":
        df = pd.read_csv(buffer, sep=None, engine="python", dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(buffer, dtype=str, keep_default_na=False)

    columns = tuple(_dedupe_columns(df.columns))
    guessed = OperationType.ESTOQUE if looks_like_stock_model(columns) else OperationType.CADASTRO
    operation = normalize_operation(selected_operation) if selected_operation else guessed
    return ModelContract(operation=operation, columns=columns, source_filename=filename), df


def align_to_contract(rows: list[dict[str, object]], contract: ModelContract) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in rows:
        records.append({col: row.get(col, "") for col in contract.columns})
    return pd.DataFrame(records, columns=list(contract.columns))


def requested_column_groups(columns: Iterable[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "name": [],
        "sku": [],
        "gtin": [],
        "price": [],
        "stock": [],
        "deposit": [],
        "brand": [],
        "supplier": [],
        "category": [],
        "images": [],
        "url": [],
        "ncm": [],
    }
    for col in columns:
        low = col.lower()
        if any(x in low for x in ("descrição", "descricao", "nome", "produto")):
            groups["name"].append(col)
        if any(x in low for x in ("sku", "código", "codigo", "referência", "referencia", "ref")):
            groups["sku"].append(col)
        if any(x in low for x in ("gtin", "ean", "código de barras", "codigo de barras")):
            groups["gtin"].append(col)
        if any(x in low for x in ("preço", "preco", "valor")):
            groups["price"].append(col)
        if any(x in low for x in ("estoque", "quantidade", "saldo", "balanço", "balanco")):
            groups["stock"].append(col)
        if any(x in low for x in ("depósito", "deposito")):
            groups["deposit"].append(col)
        if "marca" in low:
            groups["brand"].append(col)
        if "fornecedor" in low:
            groups["supplier"].append(col)
        if "categoria" in low:
            groups["category"].append(col)
        if any(x in low for x in ("imagem", "foto")):
            groups["images"].append(col)
        if "url" in low or "link" in low:
            groups["url"].append(col)
        if "ncm" in low:
            groups["ncm"].append(col)
    return groups
