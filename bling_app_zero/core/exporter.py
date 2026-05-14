from __future__ import annotations

from io import BytesIO
from typing import Sequence

import pandas as pd

from bling_app_zero.features.download_pipeline import normalize_image_urls
from bling_app_zero.features.runtime import run_features_for_stage


def _clean_contract_columns(contract_columns: Sequence[object] | None) -> list[str]:
    if not contract_columns:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for column in contract_columns:
        text = str(column or '').strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def _contract_from_input_df(df: pd.DataFrame | None, contract_columns: Sequence[object] | None) -> list[str]:
    explicit = _clean_contract_columns(contract_columns)
    if explicit:
        return explicit
    if isinstance(df, pd.DataFrame):
        return _clean_contract_columns(list(df.columns))
    return []


def enforce_export_contract(df: pd.DataFrame | None, contract_columns: Sequence[object] | None = None) -> pd.DataFrame:
    """Aplica a trava final do contrato antes do CSV.

    O download pode passar por features de limpeza/defaults depois do preview.
    Esta função é a última barreira: remove qualquer coluna fora do contrato,
    recria colunas ausentes vazias e preserva exatamente a ordem do modelo ativo.
    """
    columns = _clean_contract_columns(contract_columns)
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(columns=columns)
    out = df.copy().fillna('')
    if not columns:
        return out
    return out.reindex(columns=columns, fill_value='')


def sanitize_for_bling(
    df: pd.DataFrame,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
) -> pd.DataFrame:
    """Sanitiza o DataFrame final usando o runtime oficial BLINGMODULE.

    Regra de exportação:
    - o DataFrame que chega aqui já deve estar no modelo ativo do Bling;
    - features podem limpar valores;
    - features não podem alterar o contrato final do CSV;
    - se nenhum contrato explícito vier, o contrato é o cabeçalho recebido.
    """
    if df is None:
        return enforce_export_contract(None, contract_columns)

    contract = _contract_from_input_df(df, contract_columns)
    context = run_features_for_stage(
        operation=str(operation or 'global').strip().lower() or 'global',
        stage='download',
        final_df=df.copy().fillna(''),
    )
    safe = context.final_df if isinstance(context.final_df, pd.DataFrame) else df.copy().fillna('')
    return enforce_export_contract(safe.fillna(''), contract)


def to_bling_csv_bytes(
    df: pd.DataFrame,
    operation: str = 'global',
    contract_columns: Sequence[object] | None = None,
) -> bytes:
    safe = sanitize_for_bling(df, operation=operation, contract_columns=contract_columns)
    buffer = BytesIO()
    safe.to_csv(buffer, sep=';', index=False, encoding='utf-8-sig')
    return buffer.getvalue()


def filename_for_operation(operation: str) -> str:
    op = str(operation or 'bling').lower().strip()
    if op == 'estoque':
        return 'bling_atualizacao_estoque.csv'
    if op == 'cadastro':
        return 'bling_cadastro_produtos.csv'
    return 'bling_exportacao.csv'


__all__ = [
    'enforce_export_contract',
    'filename_for_operation',
    'normalize_image_urls',
    'sanitize_for_bling',
    'to_bling_csv_bytes',
]