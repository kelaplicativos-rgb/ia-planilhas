from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_locked_fields_runtime.py'
LOCKED_MAPPING_FIELDS_KEY = 'mapeiaai_locked_mapping_fields_v1'
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'
ALERT_MARK = '⚠️'
BALL_MARKS = ('🟢', '🟡', '🔴', '⚪')


def _audit(event: str, *, status: str = 'OK', details: dict[str, Any] | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(event, area='UNIVERSAL', status=status, details={**(details or {}), 'responsible_file': RESPONSIBLE_FILE})
    except Exception:
        pass


def _norm(value: object) -> str:
    text = str(value or '').lower()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '', text)


def _word_tuple(value: object) -> tuple[str, ...]:
    text = str(value or '').strip().casefold()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return tuple(part for part in re.split(r'[^a-z0-9]+', text) if part)


def _short_hash(value: str, size: int = 8) -> str:
    return hashlib.sha256(str(value or '').encode('utf-8')).hexdigest()[:size]


def _shared_short_hash(shared_mapping: Any, value: str, size: int = 8) -> str:
    func = getattr(shared_mapping, 'short_hash', None)
    if callable(func):
        try:
            return str(func(value, size=size))
        except TypeError:
            return str(func(value))[:size]
        except Exception:
            pass
    return _short_hash(value, size=size)


def _shared_mapping_widget_key(shared_mapping: Any, key_prefix: str, signature: str, index: int, target_name: str) -> str:
    func = getattr(shared_mapping, 'mapping_widget_key', None)
    if callable(func):
        try:
            return str(func(key_prefix, signature, index, target_name))
        except Exception:
            pass
    return f'{key_prefix}_map_{index}_{_shared_short_hash(shared_mapping, signature + target_name)}'


def _shared_fixed_widget_key(shared_mapping: Any, key_prefix: str, signature: str, index: int, target_name: str) -> str:
    func = getattr(shared_mapping, 'fixed_widget_key', None)
    if callable(func):
        try:
            return str(func(key_prefix, signature, index, target_name))
        except Exception:
            pass
    return f'{_shared_mapping_widget_key(shared_mapping, key_prefix, signature, index, target_name)}_fixed_value'


def _shared_auto_green_state_key(shared_mapping: Any, mapping_state_key: str, signature: str) -> str:
    func = getattr(shared_mapping, '_auto_green_state_key', None)
    if callable(func):
        try:
            return str(func(mapping_state_key, signature))
        except Exception:
            pass
    return f'{mapping_state_key}_auto_green_{_shared_short_hash(shared_mapping, signature, size=10)}'


def _is_fixed_mapping_value(shared_mapping: Any, value: object) -> bool:
    func = getattr(shared_mapping, 'is_fixed_value', None)
    if callable(func):
        try:
            return bool(func(value))
        except Exception:
            pass
    return str(value or '').startswith(FIXED_VALUE_PREFIX)


def _exact_green_matches(source: pd.DataFrame, target: pd.DataFrame) -> list[tuple[int, str, str]]:
    if not isinstance(source, pd.DataFrame) or not isinstance(target, pd.DataFrame):
        return []
    source_columns = [str(column) for column in source.columns]
    target_columns = [str(column) for column in target.columns]
    by_key: dict[tuple[str, ...], list[str]] = {}
    for source_column in source_columns:
        key = _word_tuple(source_column)
        if key:
            by_key.setdefault(key, []).append(source_column)
    matches: list[tuple[int, str, str]] = []
    for index, target_name in enumerate(target_columns):
        candidates = by_key.get(_word_tuple(target_name), [])
        if len(candidates) == 1:
            matches.append((index, target_name, candidates[0]))
    return matches


def _sync_auto_green_widget_values(
    st: Any,
    shared_mapping: Any,
    source: pd.DataFrame,
    target: pd.DataFrame,
    *,
    signature: str,
    mapping_state_key: str,
    key_prefix: str,
) -> None:
    if not isinstance(source, pd.DataFrame) or not isinstance(target, pd.DataFrame):
        return
    source_columns = [str(column) for column in source.columns]
    target_columns = [str(column) for column in target.columns]
    auto_green_key = _shared_auto_green_state_key(shared_mapping, mapping_state_key, signature)
    sync_key = f'{auto_green_key}_widget_sync_v3_unlocked_pages_only'
    if not bool(st.session_state.get(auto_green_key)):
        st.session_state.pop(sync_key, None)
        return
    auto_signature = f'{signature}:{len(target_columns)}:{len(source_columns)}:{_shared_short_hash(shared_mapping, "|".join(target_columns + source_columns), 12)}'
    if st.session_state.get(sync_key) == auto_signature:
        return

    current = dict(st.session_state.get(mapping_state_key) or {})
    applied = 0
    synced_widgets = 0
    for index, target_name, source_column in _exact_green_matches(source, target):
        current_value = str(current.get(target_name, '') or '')
        if _is_fixed_mapping_value(shared_mapping, current_value) or current_value == source_column:
            continue
        current[target_name] = source_column
        widget_key = _shared_mapping_widget_key(shared_mapping, key_prefix, signature, index, target_name)
        fixed_key = _shared_fixed_widget_key(shared_mapping, key_prefix, signature, index, target_name)
        st.session_state[widget_key] = source_column
        st.session_state.pop(fixed_key, None)
        applied += 1
        synced_widgets += 1
    st.session_state[mapping_state_key] = current
    st.session_state[sync_key] = auto_signature
    _audit('auto_green_exact_bind_applied_unlocked_pages_only', details={'applied_fields': int(applied), 'synced_widgets': int(synced_widgets), 'total_unlocked_target_fields': int(len(target_columns)), 'mapping_state_key': mapping_state_key, 'auto_green_key': auto_green_key})


def _is_import_alert_field(field: object) -> bool:
    key = _norm(field)
    if not key:
        return False
    if 'categoria' in key or 'category' in key or 'departamento' in key:
        return True
    if key in {'grupo', 'subgrupo'}:
        return True
    if 'tag' in key or 'etiqueta' in key:
        return True
    if 'codigopai' in key or 'codpai' in key or 'skupai' in key or key in {'pai', 'idpai'}:
        return True
    return False


def _alert_next_to_ball(label: object) -> str:
    text = str(label or '')
    if ALERT_MARK in text:
        return text
    stripped = text.lstrip()
    if not stripped:
        return text
    leading_spaces = text[: len(text) - len(stripped)]
    for ball in BALL_MARKS:
        if stripped.startswith(ball):
            rest = stripped[len(ball):].lstrip()
            return f'{leading_spaces}{ball}{ALERT_MARK} {rest}'.rstrip()
    return text


def _manual_options_first(shared_mapping: Any, options: list[Any]) -> list[str]:
    empty_option = str(getattr(shared_mapping, 'EMPTY_OPTION', '(deixar vazio)'))
    write_option = str(getattr(shared_mapping, 'WRITE_OPTION', '✍️ escrever valor fixo/manual'))
    raw_options = [str(option) for option in list(options or [])]
    ordered: list[str] = []
    seen: set[str] = set()
    for special in (empty_option, write_option):
        if special not in seen:
            ordered.append(special)
            seen.add(special)
    for option in raw_options:
        if option not in seen:
            ordered.append(option)
            seen.add(option)
    return ordered


def _patch_visual_import_alerts(shared_mapping: Any) -> None:
    if getattr(shared_mapping, '_mapeiaai_import_alert_visual_patched', False):
        return

    original_guard = getattr(shared_mapping, '_render_bling_import_guard', None)
    original_confidence_flag = getattr(shared_mapping, 'confidence_flag', None)
    original_ranked_options = getattr(shared_mapping, '_ranked_source_options', None)

    def render_bling_import_guard_visual_only(*_args: Any, **_kwargs: Any) -> None:
        return None

    if callable(original_guard):
        shared_mapping._render_bling_import_guard = render_bling_import_guard_visual_only

    if callable(original_confidence_flag):
        def confidence_flag_with_visual_alert(target: str, source_column: str, source: pd.DataFrame) -> str:
            base = str(original_confidence_flag(target, source_column, source) or '')
            return _alert_next_to_ball(base) if _is_import_alert_field(target) else base

        shared_mapping.confidence_flag = confidence_flag_with_visual_alert

    if callable(original_ranked_options):
        def ranked_source_options_with_visual_alert(
            target_name: str,
            current_value: str,
            source_columns: list[str],
            suggestions_index: dict[str, dict[str, Any]],
            source_profiles: dict[str, dict[str, float]] | None = None,
        ) -> tuple[list[str], dict[str, str]]:
            options, labels = original_ranked_options(target_name, current_value, source_columns, suggestions_index, source_profiles)
            options = _manual_options_first(shared_mapping, list(options or []))
            labels = dict(labels or {})
            if _is_import_alert_field(target_name):
                labels = {str(option): _alert_next_to_ball(label) for option, label in labels.items()}
            return options, labels

        shared_mapping._ranked_source_options = ranked_source_options_with_visual_alert

    shared_mapping._mapeiaai_import_alert_visual_patched = True
    _audit('mapping_import_alert_visual_only_installed', details={'alert_mark': ALERT_MARK, 'visual_only': True, 'manual_options_first': True, 'patched_guard': callable(original_guard), 'patched_confidence_flag': callable(original_confidence_flag), 'patched_ranked_options': callable(original_ranked_options)})


def _fixed_display(value: str) -> str:
    text = str(value or '').strip()
    if text.startswith(FIXED_VALUE_PREFIX):
        return 'FIXO: ' + text[len(FIXED_VALUE_PREFIX):].strip()
    return text or '(vazio)'


def _locked_fields(st: Any, key_prefix: str, target: pd.DataFrame) -> dict[str, dict[str, str]]:
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
            reason = str(data.get('reason') or 'Regra inteligente')
            kind = str(data.get('kind') or 'rule')
        else:
            value = str(data or '')
            reason = 'Regra inteligente'
            kind = 'rule'
        if value:
            out[field_name] = {'value': value, 'reason': reason, 'kind': kind}
    return out


def _render_locked_summary(st: Any, locked: dict[str, dict[str, str]]) -> None:
    if not locked:
        return
    st.info('🔒 Campos controlados pelas Regras e recursos inteligentes ficam somente para visualização no mapeamento. O usuário não pode trocar, deixar vazio nem escrever outro valor nesses campos.')
    rows = []
    for field, data in locked.items():
        rows.append({'Campo travado': field, 'Origem/valor aplicado': _fixed_display(data.get('value', '')), 'Motivo': data.get('reason', '')})
    with st.expander('Ver campos travados pelas regras inteligentes', expanded=True):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(360, 80 + len(rows) * 35))


def _target_without_locked(target: pd.DataFrame, locked: dict[str, dict[str, str]]) -> pd.DataFrame:
    if not isinstance(target, pd.DataFrame) or not locked:
        return target
    columns = [column for column in target.columns if str(column) not in locked]
    return target.loc[:, columns].copy() if columns else pd.DataFrame(columns=[])


def _clear_locked_widget_state(st: Any, shared_mapping: Any, target: pd.DataFrame, locked: dict[str, dict[str, str]], *, key_prefix: str, signature: str) -> None:
    if not isinstance(target, pd.DataFrame) or not locked:
        return
    all_target_columns = [str(column) for column in target.columns]
    for field in locked:
        if field not in all_target_columns:
            continue
        index = all_target_columns.index(field)
        st.session_state.pop(_shared_mapping_widget_key(shared_mapping, key_prefix, signature, index, field), None)
        st.session_state.pop(_shared_fixed_widget_key(shared_mapping, key_prefix, signature, index, field), None)


def _apply_locked_mapping_state(st: Any, mapping_state_key: str, locked: dict[str, dict[str, str]]) -> dict[str, str]:
    current = dict(st.session_state.get(mapping_state_key) or {})
    for field, data in locked.items():
        current[str(field)] = str(data.get('value') or '')
    st.session_state[mapping_state_key] = current
    return current


def install() -> None:
    try:
        from bling_app_zero.ui import shared_mapping
        import streamlit as st
    except Exception as exc:
        _audit('mapping_locked_fields_runtime_import_failed', status='AVISO', details={'error': str(exc)[:220]})
        return

    _patch_visual_import_alerts(shared_mapping)

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
        if locked:
            _apply_locked_mapping_state(st, mapping_state_key, locked)
            _clear_locked_widget_state(st, shared_mapping, target, locked, key_prefix=key_prefix, signature=signature)
            _render_locked_summary(st, locked)

        unlocked_target = _target_without_locked(target, locked)
        _sync_auto_green_widget_values(
            st,
            shared_mapping,
            source,
            unlocked_target,
            signature=signature,
            mapping_state_key=mapping_state_key,
            key_prefix=key_prefix,
        )

        if isinstance(unlocked_target, pd.DataFrame) and len(unlocked_target.columns) == 0:
            final_mapping = _apply_locked_mapping_state(st, mapping_state_key, locked)
            _audit('mapping_rule_locked_fields_only_read_only', details={'locked_fields': list(locked.keys()), 'mapping_state_key': mapping_state_key})
            return dict(final_mapping or {})

        edited = original(
            source,
            unlocked_target,
            signature=signature,
            mapping_state_key=mapping_state_key,
            engine_state_key=engine_state_key,
            key_prefix=key_prefix,
            ai_enabled=ai_enabled,
        )
        final_mapping = dict(edited or {})
        for field, data in locked.items():
            final_mapping[str(field)] = str(data.get('value') or '')
        st.session_state[mapping_state_key] = final_mapping
        _audit('mapping_rule_locked_fields_applied_read_only', details={'locked_fields': list(locked.keys()), 'unlocked_fields_count': int(len(unlocked_target.columns)) if isinstance(unlocked_target, pd.DataFrame) else 0, 'mapping_state_key': mapping_state_key, 'read_only': True, 'user_can_edit_locked_fields': False})
        return dict(final_mapping or {})

    shared_mapping.render_shared_contract_mapping = render_shared_contract_mapping_locked
    shared_mapping._mapeiaai_locked_fields_runtime_patched = True
    _audit('mapping_locked_fields_runtime_installed', details={'strategy': 'smart_rule_fields_are_read_only_and_removed_from_editable_selectboxes', 'user_can_edit_locked_fields': False})


__all__ = ['install']
