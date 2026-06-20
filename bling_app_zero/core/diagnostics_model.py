from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/diagnostics_model.py'

DEFAULT_DATA_KEYS = (
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_atualizacao_preco',
    'df_site_bruto_universal',
    'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha_atualizacao_preco',
    'df_origem_site_como_planilha_universal',
    'cadastro_wizard_df_origem',
    'cadastro_wizard_df_para_mapear',
    'df_origem',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_origem_cadastro',
    'df_origem_estoque',
    'df_origem_universal',
    'df_origem_cadastro_precificada',
    'df_final_cadastro_preview_rules_applied',
    'df_final_cadastro',
    'df_final_estoque',
    'df_final_universal',
    'df_final_download',
    'df_final_download_snapshot',
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


def _operation_from_state(state: Mapping[str, Any]) -> str:
    return str(
        state.get('direct_bling_operation_choice')
        or state.get('home_slim_flow_operation')
        or state.get('operacao_final')
        or state.get('tipo_operacao_final')
        or state.get('tipo_operacao')
        or '-'
    )


def _origin_from_state(state: Mapping[str, Any]) -> str:
    return str(
        state.get('home_slim_flow_origin')
        or state.get('frontpage_origin_radio_universal')
        or state.get('origem_final')
        or state.get('origem_tipo')
        or '-'
    )


def build_diagnostic_snapshot(state: Mapping[str, Any], *, data_keys: tuple[str, ...] = DEFAULT_DATA_KEYS) -> DiagnosticSnapshot:
    active_flow = str(state.get('home_active_operation_v2') or 'home')
    step = str(state.get('bling_wizard_step') or state.get('home_wizard_step') or '-')
    operation = _operation_from_state(state)
    origin = _origin_from_state(state)
    items: list[DiagnosticItem] = []
    seen: set[str] = set()

    for key in data_keys:
        size = dataframe_like_size(state.get(key))
        if size and key not in seen:
            seen.add(key)
            items.append(DiagnosticItem(key=key, label=key, value=size))

    # BLINGFIX: pega também DataFrames novos que ainda não entraram na lista fixa.
    for key, value in state.items():
        text_key = str(key or '')
        if text_key in seen:
            continue
        if not (text_key.startswith(('df_', 'cadastro_wizard_df_', 'estoque_wizard_df_')) or '_df_' in text_key):
            continue

        size = dataframe_like_size(value)
        if size:
            seen.add(text_key)
            items.append(DiagnosticItem(key=text_key, label=text_key, value=size))

    return DiagnosticSnapshot(active_flow, step, operation, origin, tuple(items))


__all__ = [
    'DEFAULT_DATA_KEYS',
    'DiagnosticItem',
    'DiagnosticSnapshot',
    'build_diagnostic_snapshot',
    'dataframe_like_size',
]
