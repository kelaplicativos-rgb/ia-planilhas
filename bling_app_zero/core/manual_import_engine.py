from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bling_app_zero.core.manual_import_state import (
    STATUS_DONE,
    STATUS_ERROR,
    ManualImportRequest,
    ManualImportResult,
    ManualImportState,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/manual_import_engine.py'

DATA_KEY_BY_OPERATION = {
    'universal': 'df_site_bruto_universal',
    'cadastro': 'df_site_bruto_cadastro',
    'estoque': 'df_site_bruto_estoque',
    'atualizacao_preco': 'df_site_bruto_preco',
}

ORIGIN_KEY_BY_OPERATION = {
    'universal': 'df_origem_site_como_planilha_universal',
    'cadastro': 'df_origem_site_como_planilha_cadastro',
    'estoque': 'df_origem_site_como_planilha_estoque',
    'atualizacao_preco': 'df_origem_site_como_planilha_preco',
}


@dataclass(frozen=True)
class ManualImportCommandResult:
    state: ManualImportState
    data_key: str = ''
    origin_key: str = ''
    message: str = ''
    needs_rerun: bool = False


def normalize_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'estoque', 'stock', 'estoque_site', 'atualizacao_estoque', 'atualização de estoque'}:
        return 'universal'
    if text in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return 'universal'
    if text in {'preco', 'preço', 'atualizacao_preco', 'atualização de preço'}:
        return 'universal'
    return text or 'universal'


def data_key_for_operation(operation: object) -> str:
    return DATA_KEY_BY_OPERATION.get(normalize_operation(operation), 'df_site_bruto_universal')


def origin_key_for_operation(operation: object) -> str:
    return ORIGIN_KEY_BY_OPERATION.get(normalize_operation(operation), 'df_origem_site_como_planilha_universal')


def _shape(value: Any) -> tuple[int, int]:
    shape = getattr(value, 'shape', None)
    if isinstance(shape, tuple) and len(shape) >= 2:
        return int(shape[0] or 0), int(shape[1] or 0)
    columns = getattr(value, 'columns', None)
    if columns is not None:
        try:
            return len(value), len(columns)
        except Exception:
            return 0, 0
    return 0, 0


def _columns(value: Any) -> tuple[str, ...]:
    columns = getattr(value, 'columns', None)
    if columns is None:
        return tuple()
    try:
        return tuple(str(col) for col in list(columns))
    except Exception:
        return tuple()


def finish_manual_import(
    request: ManualImportRequest,
    data: Any,
    *,
    recovery_messages: tuple[str, ...] | list[str] = (),
) -> ManualImportCommandResult:
    rows, _cols = _shape(data)
    columns = _columns(data)
    operation = normalize_operation(request.operation)
    data_key = data_key_for_operation(operation)
    origin_key = origin_key_for_operation(operation)
    if rows <= 0:
        message = 'Não encontrei uma tabela ou blocos de produtos no conteúdo enviado.'
        result = ManualImportResult(status=STATUS_ERROR, error=message, message=message, raw_label=request.raw_label, recovery_messages=tuple(recovery_messages or ()))
        return ManualImportCommandResult(ManualImportState(request=request, result=result), data_key, origin_key, message, False)
    message = f'Origem universal criada com {rows} linha(s) e {len(columns)} coluna(s).'
    result = ManualImportResult(
        status=STATUS_DONE,
        rows=rows,
        columns=columns,
        data_key=data_key,
        origin_key=origin_key,
        raw_label=request.raw_label,
        message=message,
        recovery_messages=tuple(str(item) for item in list(recovery_messages or ()) if str(item or '').strip()),
    )
    return ManualImportCommandResult(ManualImportState(request=request, result=result), data_key, origin_key, message, True)


def build_manual_import_report(result: ManualImportCommandResult) -> dict[str, Any]:
    return {
        'status': result.state.result.status,
        'message': result.message,
        'rows': result.state.result.rows,
        'columns': list(result.state.result.columns),
        'data_key': result.data_key,
        'origin_key': result.origin_key,
        'raw_label': result.state.result.raw_label,
        'operation': result.state.request.operation,
        'source_type': result.state.request.source_type,
        'recovery_messages': list(result.state.result.recovery_messages),
    }


__all__ = [
    'DATA_KEY_BY_OPERATION',
    'ORIGIN_KEY_BY_OPERATION',
    'ManualImportCommandResult',
    'build_manual_import_report',
    'data_key_for_operation',
    'finish_manual_import',
    'normalize_operation',
    'origin_key_for_operation',
]
