from __future__ import annotations

from typing import Any

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_locked_fields_runtime.py'
LOCKED_MAPPING_FIELDS_KEY = 'mapeiaai_locked_mapping_fields_v1'
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'


def _audit(event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='UNIVERSAL', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def _fixed_display(value: str) -> str:
    text = str(value or '').strip()
    if text.startswith(FIXED_VALUE_PREFIX):
        return 'FIXO: ' + text[len(FIXED_VALUE_PREFIX):].strip()
    return text or '(vazio)'


def _locked_fields(st, key_prefix: str, target: pd.DataFrame) -> dict[str, dict[str, str]]:
    raw = st.session_state.get(f'{key_prefix}_locked_mapping_fields_v1') or st.session_state.get(LOCKED_MAPPING_FIELDS_KEY) or {}
    if not isinstance(raw, dict) or not isinstance(target, pd.DataFrame):
        return {}
    target_columns = {str(column) for column in target.columns}
    out: dict[str, dict[str, str]] = {}
    for field, data in raw.items():
        field_name = str(field)
        if field_name not in target_columns:
            continue
        if isinstance(data, dict):
            value = str(data.get('value') or '')
            reason = str(data.get('reason') or 'Tratado pelas regras inteligentes')
            kind = str(data.get('kind') or 'rule')
        else:
            value = str(data or '')
            reason = 'Tratado pelas regras inteligentes'
            kind = 'rule'
        out[field_name] = {'value': value, 'reason': reason, 'kind': kind}
    return out


def _render_locked_summary(st, locked: dict[str, dict[str, str]]) -> None:
    if not locked:
        return
    st.info('🔒 Alguns campos foram bloqueados porque serão preenchidos/tratados pelas Regras e recursos inteligentes.')
    rows = []
    for field, data in locked.items():
        rows.append({'Campo bloqueado': field, 'Origem/valor usado': _fixed_display(data.get('value', '')), 'Motivo': data.get('reason', '')})
    with st.expander('Ver campos bloqueados pelas regras', expanded=False):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(320, 80 + len(rows) * 35))


def install() -> None:
    try:
        from bling_app_zero.ui import shared_mapping
        import streamlit as st
    except Exception as exc:
        _audit('mapping_locked_fields_runtime_import_failed', status='AVISO', details={'error': str(exc)[:220]})
        return

    if getattr(shared_mapping, '_mapeiaai_locked_fields_runtime_patched', False):
        return

    original = shared_mapping.render_shared_contract_mapping

    def render_shared_contract_mapping_locked(
        source: pd.DataFrame,
        target: pd.DataFrame,
        *,
        signature: str,
        mapping_state_key: str,
        engine_state_key: str,
        key_prefix: str = 'mapeiaai_shared',
        ai_enabled: bool = True,
    ) -> dict[str, str]:
        locked = _locked_fields(st, key_prefix, target)
        if not locked:
            return original(source, target, signature=signature, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key, key_prefix=key_prefix, ai_enabled=ai_enabled)

        current = dict(st.session_state.get(mapping_state_key) or {})
        for field, data in locked.items():
            current[field] = str(data.get('value') or '')
        st.session_state[mapping_state_key] = current

        _render_locked_summary(st, locked)
        editable_columns = [column for column in target.columns if str(column) not in locked]
        if editable_columns:
            editable_target = target.loc[:, editable_columns].copy()
            edited = original(source, editable_target, signature=signature, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key, key_prefix=key_prefix, ai_enabled=ai_enabled)
        else:
            st.success('Todos os campos deste modelo foram tratados pelas regras inteligentes. Não há campos manuais para revisar.')
            edited = {}

        combined = dict(edited or {})
        for field, data in locked.items():
            combined[field] = str(data.get('value') or '')
        st.session_state[mapping_state_key] = combined
        _audit('mapping_locked_fields_applied', details={'locked_fields': list(locked.keys()), 'editable_fields': len(editable_columns), 'mapping_state_key': mapping_state_key})
        return combined

    shared_mapping.render_shared_contract_mapping = render_shared_contract_mapping_locked
    shared_mapping._mapeiaai_locked_fields_runtime_patched = True
    _audit('mapping_locked_fields_runtime_installed', details={'strategy': 'locked_fields_removed_from_manual_mapping'})


__all__ = ['install']
