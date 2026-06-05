from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.cadastro_wizard_state import (
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
    clear_cadastro_outputs_if_source_changed,
    set_context_final_df,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_bridge.py'
BRIDGE_SOURCE_KEY = 'mirror_bridge_source'
BRIDGE_OPERATION_KEY = 'mirror_bridge_operation'
BRIDGE_SUMMARY_KEY = 'mirror_bridge_summary'
BRIDGE_READY_KEY = 'mirror_bridge_ready_for_official_flow'
BRIDGE_TARGET_STEP_KEY = 'mirror_bridge_target_step'


@dataclass(frozen=True)
class MirrorBridgeResult:
    ok: bool
    operation: str
    rows: int
    columns: int
    target_step: str
    message: str
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _valid_df(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty


def bridge_reviewed_dataframe_to_official_flow(
    df: pd.DataFrame,
    *,
    operation: str,
    source_label: str,
    target_step: str,
) -> MirrorBridgeResult:
    """Prepara uma base revisada do espelhamento para o fluxo oficial.

    Esta função não envia nada para API e não baixa arquivo final. Ela apenas
    coloca a base revisada como origem/final temporária para o usuário seguir
    pelo preview/download/envio oficial, mantendo validações e logs.
    """
    op = str(operation or '').strip().lower() or 'universal'
    target = str(target_step or '').strip().lower() or 'preview'
    label = str(source_label or 'espelhamento').strip()

    if not _valid_df(df):
        result = MirrorBridgeResult(False, op, 0, 0, target, 'Nenhuma base revisada válida para preparar.')
        add_audit_event('mirror_bridge_no_valid_dataframe', area='ESPELHAMENTO', status='BLOQUEADO', details=result.to_dict())
        return result

    fixed = df.copy().fillna('')
    clear_cadastro_outputs_if_source_changed(fixed)
    st.session_state[CADASTRO_ORIGEM_KEY] = fixed.copy()
    st.session_state[CADASTRO_ORIGEM_PRICED_KEY] = fixed.copy()
    set_context_final_df(fixed.copy())

    summary = {
        'operation': op,
        'source_label': label,
        'rows': int(len(fixed)),
        'columns': int(len(fixed.columns)),
        'target_step': target,
        'responsible_file': RESPONSIBLE_FILE,
    }
    st.session_state[BRIDGE_SOURCE_KEY] = label
    st.session_state[BRIDGE_OPERATION_KEY] = op
    st.session_state[BRIDGE_SUMMARY_KEY] = summary
    st.session_state[BRIDGE_READY_KEY] = True
    st.session_state[BRIDGE_TARGET_STEP_KEY] = target
    st.session_state['home_slim_flow_origin'] = 'site'
    st.session_state['origem_final'] = 'site'
    st.session_state['home_detected_operation'] = op
    st.session_state['operacao_final'] = op
    st.session_state['tipo_operacao_final'] = op

    result = MirrorBridgeResult(True, op, int(len(fixed)), int(len(fixed.columns)), target, 'Base revisada preparada para o fluxo oficial.')
    add_audit_event('mirror_bridge_prepared_official_flow', area='ESPELHAMENTO', status='OK', details=result.to_dict() | {'summary': summary})
    return result


__all__ = [
    'BRIDGE_OPERATION_KEY',
    'BRIDGE_READY_KEY',
    'BRIDGE_SOURCE_KEY',
    'BRIDGE_SUMMARY_KEY',
    'BRIDGE_TARGET_STEP_KEY',
    'MirrorBridgeResult',
    'bridge_reviewed_dataframe_to_official_flow',
]
