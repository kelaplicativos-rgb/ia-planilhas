from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import pandas as pd

from bling_app_zero.core.bling_mirror_config import MIRROR_MODE_BOTH, MIRROR_MODE_NEW_PRODUCTS, MIRROR_MODE_STOCK, MirrorMonitorConfig
from bling_app_zero.flows.site_operation_router import run_site_engine
from bling_app_zero.pipelines.site_pipeline import run_pipeline as run_site_pipeline

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_extract.py'
STOCK_COLUMNS = ['id', 'codigo', 'sku', 'gtin', 'estoque', 'quantidade', 'deposito', 'url']
NEW_PRODUCT_COLUMNS = ['nome', 'descricao', 'descricao_curta', 'preco', 'estoque', 'codigo', 'sku', 'gtin', 'marca', 'categoria', 'imagens', 'url']
BOTH_COLUMNS = list(dict.fromkeys([*NEW_PRODUCT_COLUMNS, *STOCK_COLUMNS]))


@dataclass(frozen=True)
class MirrorExtractResult:
    ok: bool
    message: str
    operation: str
    requested_columns: tuple[str, ...]
    rows: int
    columns: int
    dataframe: pd.DataFrame
    errors: tuple[str, ...] = tuple()
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self, *, include_dataframe: bool = False) -> dict[str, Any]:
        data = asdict(self)
        data['requested_columns'] = list(self.requested_columns)
        data['errors'] = list(self.errors)
        if include_dataframe:
            data['dataframe'] = self.dataframe.fillna('').to_dict(orient='records') if isinstance(self.dataframe, pd.DataFrame) else []
        else:
            data.pop('dataframe', None)
        return data


def columns_for_mirror_mode(mode: str) -> list[str]:
    normalized = str(mode or '').strip().lower()
    if normalized == MIRROR_MODE_STOCK:
        return list(STOCK_COLUMNS)
    if normalized == MIRROR_MODE_NEW_PRODUCTS:
        return list(NEW_PRODUCT_COLUMNS)
    if normalized == MIRROR_MODE_BOTH:
        return list(BOTH_COLUMNS)
    return list(STOCK_COLUMNS)


def operation_for_mirror_mode(mode: str) -> str:
    normalized = str(mode or '').strip().lower()
    if normalized == MIRROR_MODE_NEW_PRODUCTS:
        return 'cadastro'
    return 'estoque'


def read_mirror_site_products(config: MirrorMonitorConfig | Mapping[str, Any], *, raw_urls: str = '') -> MirrorExtractResult:
    cfg = config if isinstance(config, MirrorMonitorConfig) else MirrorMonitorConfig(**{key: value for key, value in dict(config or {}).items() if key in MirrorMonitorConfig.__dataclass_fields__})
    cfg = cfg.normalized()
    urls = str(raw_urls or cfg.site_url or '').strip()
    if not urls:
        return MirrorExtractResult(False, 'Nenhum site informado para leitura monitorada.', operation_for_mirror_mode(cfg.mode), tuple(), 0, 0, pd.DataFrame(), ('site_url vazio',))

    requested_columns = columns_for_mirror_mode(cfg.mode)
    operation = operation_for_mirror_mode(cfg.mode)
    try:
        df = run_site_engine(
            operation=operation,
            pipeline=run_site_pipeline,
            raw_urls=urls,
            requested_columns=requested_columns,
            all_products=True,
            max_pages=max(1, min(int(cfg.max_products_per_cycle or 1), 650)),
            max_products=max(1, min(int(cfg.max_products_per_cycle or 1), 1500)),
            progress_callback=None,
        )
        if not isinstance(df, pd.DataFrame) or df.empty:
            return MirrorExtractResult(False, 'Leitura monitorada não retornou produtos válidos.', operation, tuple(requested_columns), 0, 0, pd.DataFrame(), ('dataframe vazio',))
        clean = df.copy().fillna('')
        if cfg.deposit_name and 'deposito' not in clean.columns:
            clean['deposito'] = cfg.deposit_name
        elif cfg.deposit_name and 'deposito' in clean.columns:
            clean['deposito'] = clean['deposito'].map(lambda value: str(value or '').strip() or cfg.deposit_name)
        return MirrorExtractResult(True, f'Leitura monitorada concluída com {len(clean)} produto(s).', operation, tuple(requested_columns), int(len(clean)), int(len(clean.columns)), clean)
    except Exception as exc:
        return MirrorExtractResult(False, f'Erro na leitura monitorada: {exc}', operation, tuple(requested_columns), 0, 0, pd.DataFrame(), (exc.__class__.__name__, str(exc)))


__all__ = [
    'BOTH_COLUMNS',
    'MirrorExtractResult',
    'NEW_PRODUCT_COLUMNS',
    'STOCK_COLUMNS',
    'columns_for_mirror_mode',
    'operation_for_mirror_mode',
    'read_mirror_site_products',
]
