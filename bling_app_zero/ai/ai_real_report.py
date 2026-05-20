from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bling_app_zero.core.gtin import looks_like_gtin_column
from bling_app_zero.core.text import clean_cell, normalize_key


@dataclass(frozen=True)
class FieldReport:
    column: str
    filled: int
    empty: int
    status: str
    reason: str
    fix_step: str


@dataclass(frozen=True)
class FinalReport:
    total_rows: int
    total_columns: int
    filled_columns: int
    empty_columns: int
    field_reports: list[FieldReport]
    summary: str


def _columns(df: pd.DataFrame | None) -> list[str]:
    return [str(column) for column in df.columns] if isinstance(df, pd.DataFrame) else []


def _non_empty(value: object) -> bool:
    text = clean_cell(value)
    return bool(text and normalize_key(text) not in {'nan', 'none', 'null', 'na', 'n/a'})


def _column_kind(column: object) -> str:
    key = normalize_key(str(column or ''))
    if looks_like_gtin_column(column):
        return 'gtin'
    if any(term in key for term in ['preco', 'preço', 'valor']):
        return 'preco'
    if any(term in key for term in ['imagem', 'foto', 'image']):
        return 'imagem'
    if any(term in key for term in ['ncm', 'classificacao fiscal', 'classificação fiscal']):
        return 'ncm'
    if any(term in key for term in ['descricao', 'descrição', 'nome', 'produto', 'titulo', 'título']):
        return 'descricao'
    if any(term in key for term in ['estoque', 'quantidade', 'saldo']):
        return 'estoque'
    return 'campo'


def _reason_for_empty(column: str, kind: str, filled: int, total: int) -> str:
    if filled == 0:
        if kind == 'ncm':
            return 'O modelo pediu NCM, mas a origem não trouxe esse dado ou ele ainda não foi revisado.'
        if kind == 'imagem':
            return 'Nenhuma imagem válida foi encontrada ou ligada para este campo.'
        if kind == 'preco':
            return 'Nenhum preço foi ligado a este campo ou a origem não trouxe valor válido.'
        if kind == 'gtin':
            return 'A origem não trouxe GTIN/EAN válido ou os valores inválidos foram limpos.'
        if kind == 'estoque':
            return 'A origem não trouxe saldo/quantidade para este modelo.'
        return 'O campo ficou vazio porque não foi encontrado na origem ou não foi ligado no mapeamento.'
    if filled < total:
        return 'Parte dos produtos não tinha esse dado disponível na origem ou ficou sem preenchimento após o mapeamento.'
    return 'Campo preenchido no arquivo final.'


def _fix_step_for(kind: str, filled: int, total: int) -> str:
    if filled == total:
        return 'Nenhuma correção necessária.'
    if kind == 'preco':
        return '4. Preço ou 5. Mapear campos'
    if kind in {'descricao', 'gtin', 'imagem', 'ncm'}:
        return '6. Revisão final'
    if kind == 'estoque':
        return '3. Dados do fornecedor ou 5. Mapear campos'
    return '5. Mapear campos'


def build_final_report(df_final_universal: pd.DataFrame | None) -> FinalReport:
    if not isinstance(df_final_universal, pd.DataFrame) or df_final_universal.empty:
        return FinalReport(0, 0, 0, 0, [], 'Arquivo final ainda não gerado.')

    total_rows = len(df_final_universal)
    reports: list[FieldReport] = []
    filled_columns = 0
    empty_columns = 0
    for column in _columns(df_final_universal):
        series = df_final_universal[column]
        filled = int(series.map(_non_empty).sum())
        empty = int(total_rows - filled)
        kind = _column_kind(column)
        status = 'OK' if empty == 0 else 'Vazio' if filled == 0 else 'Parcial'
        if filled > 0:
            filled_columns += 1
        else:
            empty_columns += 1
        reports.append(FieldReport(column, filled, empty, status, _reason_for_empty(column, kind, filled, total_rows), _fix_step_for(kind, filled, total_rows)))

    summary = f'{total_rows} linha(s), {len(_columns(df_final_universal))} coluna(s), {filled_columns} coluna(s) com dados e {empty_columns} totalmente vazia(s).'
    return FinalReport(total_rows, len(_columns(df_final_universal)), filled_columns, empty_columns, reports, summary)


__all__ = ['FieldReport', 'FinalReport', 'build_final_report']