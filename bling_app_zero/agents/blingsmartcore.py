from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import pandas as pd

from bling_app_zero.agents.site_ai_validator import SmartScanQuality, evaluate_site_dataframe, normalize_site_dataframe
from bling_app_zero.core.audit import add_audit_event

OriginName = Literal['site', 'planilha', 'xml', 'pdf', 'modelo_bling', 'preview_final', 'desconhecida']
RESPONSIBLE_FILE = 'bling_app_zero/agents/blingsmartcore.py'


@dataclass(frozen=True)
class SmartCoreResult:
    origin: str
    operation: str
    rows_before: int
    rows_after: int
    columns: int
    quality: SmartScanQuality
    message: str


def _safe_origin(origin: str | None) -> str:
    text = str(origin or '').strip().lower()
    if text in {'site', 'planilha', 'xml', 'pdf', 'modelo_bling', 'preview_final'}:
        return text
    return 'desconhecida'


def apply_blingsmartcore(
    df: pd.DataFrame,
    *,
    origin: str = 'desconhecida',
    operation: str = 'universal',
    audit: bool = True,
) -> tuple[pd.DataFrame, SmartCoreResult]:
    """Normaliza e valida qualquer origem antes de seguir no fluxo.

    Aplica regras inteligentes compartilhadas para site, planilha, XML, PDF,
    modelos Bling e preview final. Não altera colunas, apenas valores.
    """
    safe_origin = _safe_origin(origin)
    if not isinstance(df, pd.DataFrame):
        empty = pd.DataFrame()
        quality = evaluate_site_dataframe(empty, operation=operation)
        result = SmartCoreResult(safe_origin, operation, 0, 0, 0, quality, 'BLINGSMARTCORE recebeu origem vazia ou inválida.')
        return empty, result

    rows_before = int(len(df))
    normalized = normalize_site_dataframe(df.copy().fillna(''))
    quality = evaluate_site_dataframe(normalized, operation=operation)
    result = SmartCoreResult(
        origin=safe_origin,
        operation=operation,
        rows_before=rows_before,
        rows_after=int(len(normalized)),
        columns=int(len(normalized.columns)),
        quality=quality,
        message=f'BLINGSMARTCORE validou {len(normalized)} linha(s) de {safe_origin} com nota {quality.score}/100.',
    )
    if audit:
        add_audit_event(
            'blingsmartcore_applied',
            area='SMARTCORE',
            step=safe_origin,
            status='OK' if quality.rows else 'AVISO',
            details={
                'origin': safe_origin,
                'operation': operation,
                'rows_before': rows_before,
                'rows_after': int(len(normalized)),
                'columns': int(len(normalized.columns)),
                'quality': asdict(quality),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    return normalized, result


def render_smartcore_notice(result: SmartCoreResult) -> str:
    quality = result.quality
    warnings = '<br>'.join(f'• {item}' for item in quality.warnings[:5])
    return (
        f'<b>BLINGSMARTCORE</b><br>'
        f'Origem: <b>{result.origin}</b> · Operação: <b>{result.operation}</b><br>'
        f'Qualidade: <b>{quality.score}/100</b> · Linhas: <b>{quality.rows}</b><br>'
        f'{warnings}'
    )


__all__ = ['SmartCoreResult', 'apply_blingsmartcore', 'render_smartcore_notice']
