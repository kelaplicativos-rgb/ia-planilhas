from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.credits import check_mapping_credit, consume_mapping_credit, credits_enabled
from bling_app_zero.ui.home_shared import df_signature
from bling_app_zero.ui.home_wizard_constants import STEP_REGRAS, WIZARD_STEP_KEY
from bling_app_zero.ui.home_wizard_scroll import set_scroll_target
from bling_app_zero.ui.mapping_confidence_state import required_targets
from bling_app_zero.ui.mapping_constants import CADASTRO_MAPPING_CONFIRMED_KEY, CADASTRO_MAPPING_SIGNATURE_KEY
from bling_app_zero.ui.mapping_widget_state import is_manual_value, manual_value_key, option_value, short_hash, target_widget_key


BLINGFIX_REQUIRED_MAX_LIST = 8


def manual_values_for_signature(mapping: dict[str, str], target_columns: list[str], mapping_key: str) -> list[str]:
    parts: list[str] = []
    for index, target in enumerate(target_columns):
        if is_manual_value(mapping.get(target, '')):
            widget_key = target_widget_key(mapping_key, index)
            parts.append(f'{target}:{st.session_state.get(manual_value_key(widget_key), "")}')
    return parts


def mapping_signature(
    mapping: dict[str, str],
    df_final: pd.DataFrame,
    target_columns: list[str] | None = None,
    mapping_key: str = '',
) -> str:
    parts = [f'{key}={mapping.get(key, "")}' for key in sorted(mapping)]
    if target_columns and mapping_key:
        parts.extend(manual_values_for_signature(mapping, target_columns, mapping_key))
    return short_hash('|'.join(parts) + ':' + df_signature(df_final), size=16)


def invalidate_confirmation_if_changed(
    mapping: dict[str, str],
    df_final: pd.DataFrame,
    target_columns: list[str],
    mapping_key: str,
) -> str:
    signature = mapping_signature(mapping, df_final, target_columns, mapping_key)
    confirmed_signature = st.session_state.get(CADASTRO_MAPPING_SIGNATURE_KEY)
    if confirmed_signature and confirmed_signature != signature:
        st.session_state.pop(CADASTRO_MAPPING_CONFIRMED_KEY, None)
        st.session_state.pop(CADASTRO_MAPPING_SIGNATURE_KEY, None)
    return signature


def _source_value(mapping_value: str | None) -> str:
    value = str(mapping_value or '').strip()
    if is_manual_value(value):
        return ''
    return option_value(value)


def _duplicated_source_columns(mapping: dict[str, str]) -> list[str]:
    values = [_source_value(value) for value in mapping.values()]
    values = [value for value in values if value]
    return sorted({value for value in values if values.count(value) > 1})


def _missing_required_targets(mapping: dict[str, str], target_columns: list[str]) -> list[str]:
    required = required_targets(target_columns)
    missing: list[str] = []
    for target in target_columns:
        if target not in required:
            continue
        value = str(mapping.get(target, '') or '').strip()
        if not value:
            missing.append(target)
    return missing


def _render_blocking_list(title: str, items: list[str]) -> None:
    if not items:
        return
    visible = items[:BLINGFIX_REQUIRED_MAX_LIST]
    st.warning(f'{title}: ' + ', '.join(visible))
    hidden_count = len(items) - len(visible)
    if hidden_count > 0:
        st.caption(f'Mais {hidden_count} item(ns) oculto(s). Ajuste os campos sinalizados para continuar.')


def _render_non_blocking_list(title: str, items: list[str]) -> None:
    if not items:
        return
    visible = items[:BLINGFIX_REQUIRED_MAX_LIST]
    st.info(f'{title}: ' + ', '.join(visible))
    hidden_count = len(items) - len(visible)
    if hidden_count > 0:
        st.caption(f'Mais {hidden_count} item(ns) oculto(s).')


def _mapping_blockers(mapping: dict[str, str], target_columns: list[str]) -> list[str]:
    blockers: list[str] = []
    missing = _missing_required_targets(mapping, target_columns)
    duplicated = _duplicated_source_columns(mapping)
    if missing:
        blockers.append('required')
        _render_blocking_list('Campos obrigatórios sem ligação', missing)
    if duplicated:
        _render_non_blocking_list('Colunas de origem repetidas permitidas', duplicated)
        st.caption('A mesma coluna de origem pode ser usada em mais de um campo quando necessário. Isso não bloqueia mais a confirmação do mapeamento.')
    return blockers


def _render_credit_status(signature: str) -> bool:
    check = check_mapping_credit(signature)
    if not check.enabled:
        return True
    if check.allowed:
        st.info(f'💳 {check.message} Saldo atual: {check.balance} crédito(s).')
        return True
    st.error(f'💳 {check.message} Saldo atual: {check.balance} crédito(s).')
    st.caption('Adicione créditos no sidebar para liberar a confirmação desta planilha mapeada.')
    return False


def render_confirm_mapping_button(
    mapping: dict[str, str],
    df_final: pd.DataFrame,
    mapping_key: str,
    target_columns: list[str],
) -> None:
    signature = invalidate_confirmation_if_changed(mapping, df_final, target_columns, mapping_key)
    confirmed = bool(st.session_state.get(CADASTRO_MAPPING_CONFIRMED_KEY)) and st.session_state.get(CADASTRO_MAPPING_SIGNATURE_KEY) == signature
    if confirmed:
        st.success('Mapeamento confirmado. Você já pode continuar para a revisão final.')
        return

    blockers = _mapping_blockers(mapping, target_columns)
    if blockers:
        st.info('Revise os campos sinalizados. A confirmação será liberada quando o mapeamento estiver válido.')
        return

    has_credit = _render_credit_status(signature)
    st.info('Revise os campos necessários e clique em Confirmar mapeamento para liberar a revisão final.')
    if st.button('Confirmar mapeamento', use_container_width=True, key=f'{mapping_key}_confirm', disabled=credits_enabled() and not has_credit):
        if not consume_mapping_credit(signature, operation='cadastro'):
            st.error('Créditos insuficientes para confirmar esta planilha mapeada.')
            return
        st.session_state[CADASTRO_MAPPING_CONFIRMED_KEY] = True
        st.session_state[CADASTRO_MAPPING_SIGNATURE_KEY] = signature
        st.session_state[WIZARD_STEP_KEY] = STEP_REGRAS
        set_scroll_target(STEP_REGRAS)
        try:
            st.query_params['step'] = STEP_REGRAS
        except Exception:
            pass
        st.success('Mapeamento confirmado.')
        st.rerun()


__all__ = [
    'invalidate_confirmation_if_changed',
    'manual_values_for_signature',
    'mapping_signature',
    'render_confirm_mapping_button',
]
