from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/diagnostics_model.py'

DEFAULT_DATA_KEYS = (
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'cadastro_wizard_df_origem',
    'cadastro_wizard_df_para_mapear',
    'df_final_download',
)


@dataclass(frozen=True)
class DiagnosticItem:
    key: str
    label: str
    value: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class DiagnosticSnapshot:
    active_flow: str
    step: str
    operation: str
    origin: str
    data_items: tuple[DiagnosticItem, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'active_flow': self.active_flow,
            'step': self.step,
            'operation': self.operation,
            'origin': self.origin,
            'data_items': [item.to_dict() for item in self.data_items],
        }


def dataframe_like_size(value: Any) -> str:
    rows = getattr(value, 'shape', None)
    if isinstance(rows, tuple) and len(rows) >= 2:
        return f'{rows[0]}x{rows[1]}'
    columns = getattr(value, 'columns', None)
    if columns is not None:
        try:
            return f'{len(value)}x{len(columns)}'
        except Exception:
            return ''
    return ''


def build_diagnostic_snapshot(state: Mapping[str, Any], *, data_keys: tuple[str, ...] = DEFAULT_DATA_KEYS) -> DiagnosticSnapshot:
    active_flow = str(state.get('home_active_operation_v2') or 'home')
    step = str(state.get('bling_wizard_step') or '-')
    operation = str(state.get('direct_bling_operation_choice') or state.get('home_slim_flow_operation') or state.get('operacao_final') or '-')
    origin = str(state.get('home_slim_flow_origin') or state.get('origem_final') or '-')
    items: list[DiagnosticItem] = []
    for key in data_keys:
        size = dataframe_like_size(state.get(key))
        if size:
            items.append(DiagnosticItem(key=key, label=key, value=size))
    return DiagnosticSnapshot(active_flow, step, operation, origin, tuple(items))


__all__ = [
    'DEFAULT_DATA_KEYS',
    'DiagnosticItem',
    'DiagnosticSnapshot',
    'build_diagnostic_snapshot',
    'dataframe_like_size',
]
