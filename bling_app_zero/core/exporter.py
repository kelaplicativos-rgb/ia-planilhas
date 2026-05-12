from __future__ import annotations

from io import BytesIO

import pandas as pd

from bling_app_zero.features.download_pipeline import normalize_image_urls
from bling_app_zero.features.runtime import run_features_for_stage


def sanitize_for_bling(df: pd.DataFrame, operation: str = 'global') -> pd.DataFrame:
    """Sanitiza o DataFrame final usando o runtime oficial BLINGMODULE.

    A lógica antiga de GTIN, imagens, medidas, regras, defaults e códigos únicos
    foi migrada para runners modulares em bling_app_zero/features/download_pipeline.py.
    Este arquivo agora atua como orquestrador de exportação.
    """
    if df is None:
        return pd.DataFrame()

    context = run_features_for_stage(
        operation=str(operation or 'global').strip().lower() or 'global',
        stage='download',
        final_df=df.copy().fillna(''),
    )
    safe = context.final_df if isinstance(context.final_df, pd.DataFrame) else df.copy().fillna('')
    return safe.fillna('')


def to_bling_csv_bytes(df: pd.DataFrame, operation: str = 'global') -> bytes:
    safe = sanitize_for_bling(df, operation=operation)
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
    'filename_for_operation',
    'normalize_image_urls',
    'sanitize_for_bling',
    'to_bling_csv_bytes',
]
