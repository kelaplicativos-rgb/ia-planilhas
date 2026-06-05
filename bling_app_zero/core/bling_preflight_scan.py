from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd

from bling_app_zero.core.operation_contract import OP_CADASTRO, OP_ESTOQUE, normalize_operation
from bling_app_zero.core.text import normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_preflight_scan.py'

_CODE_TERMS = ('codigo', 'código', 'sku', 'referencia', 'referência', 'id produto', 'id bling')
_GTIN_TERMS = ('gtin', 'ean', 'codigo de barras', 'código de barras')
_NAME_TERMS = ('nome', 'produto', 'descrição', 'descricao', 'titulo', 'título')
_QTY_TERMS = ('quantidade', 'qtd', 'saldo', 'estoque', 'balanço', 'balanco')
_IMAGE_TERMS = ('imagem', 'imagens', 'foto', 'fotos', 'url imagem')


@dataclass(frozen=True)
class BlingPreflightReport:
    operation: str
    total_rows: int
    safe_to_send_rows: int
    missing_identifier_rows: int
    missing_required_rows: int
    rows_with_images: int
    estimated_batches: int
    batch_size: int
    warnings: tuple[str, ...]
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['warnings'] = list(self.warnings)
        return data


def _normalized_columns(df: pd.DataFrame) -> dict[str, str]:
    return {normalize_key(column): str(column) for column in df.columns}


def _find_column(df: pd.DataFrame, terms: tuple[str, ...]) -> str:
    columns = _normalized_columns(df)
    normalized_terms = [normalize_key(term) for term in terms]
    for normalized, original in columns.items():
        if any(term in normalized for term in normalized_terms):
            return original
    return ''


def _filled_mask(df: pd.DataFrame, column: str) -> pd.Series:
    if not column or column not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df[column].fillna('').astype(str).str.strip().ne('')


def build_bling_preflight_report(df: pd.DataFrame, operation: str, *, batch_size: int) -> BlingPreflightReport:
    op = normalize_operation(operation)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return BlingPreflightReport(
            operation=op,
            total_rows=0,
            safe_to_send_rows=0,
            missing_identifier_rows=0,
            missing_required_rows=0,
            rows_with_images=0,
            estimated_batches=0,
            batch_size=int(batch_size or 1),
            warnings=('Nenhuma linha encontrada para envio.',),
        )

    total = int(len(df))
    safe_batch = max(1, int(batch_size or 1))
    code_col = _find_column(df, _CODE_TERMS)
    gtin_col = _find_column(df, _GTIN_TERMS)
    name_col = _find_column(df, _NAME_TERMS)
    qty_col = _find_column(df, _QTY_TERMS)
    image_col = _find_column(df, _IMAGE_TERMS)

    has_identifier = _filled_mask(df, code_col) | _filled_mask(df, gtin_col)
    has_name = _filled_mask(df, name_col)
    has_qty = _filled_mask(df, qty_col)

    if op == OP_ESTOQUE:
        required_ok = has_identifier & has_qty
    else:
        required_ok = has_identifier | has_name

    safe_rows = int(required_ok.sum())
    missing_identifier = int((~has_identifier).sum())
    missing_required = int((~required_ok).sum())
    rows_with_images = int(_filled_mask(df, image_col).sum()) if image_col else 0
    estimated_batches = int((safe_rows + safe_batch - 1) // safe_batch) if safe_rows else 0

    warnings: list[str] = []
    if total > 300:
        warnings.append('Muitas linhas detectadas; o envio foi protegido por lotes menores e checkpoint.')
    if missing_identifier:
        warnings.append(f'{missing_identifier} linha(s) sem SKU/código/GTIN; podem virar pendência ou depender de nome.')
    if missing_required:
        warnings.append(f'{missing_required} linha(s) não têm os campos mínimos para envio seguro.')
    if op == OP_CADASTRO and rows_with_images > 150:
        warnings.append('Muitas linhas com imagens; comparação/cadastro pode demorar mais.')
    if not warnings:
        warnings.append('Pré-varredura local sem bloqueios críticos.')

    return BlingPreflightReport(
        operation=op,
        total_rows=total,
        safe_to_send_rows=safe_rows,
        missing_identifier_rows=missing_identifier,
        missing_required_rows=missing_required,
        rows_with_images=rows_with_images,
        estimated_batches=estimated_batches,
        batch_size=safe_batch,
        warnings=tuple(warnings),
    )


__all__ = ['BlingPreflightReport', 'build_bling_preflight_report']
