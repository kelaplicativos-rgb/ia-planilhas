from __future__ import annotations

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


def _patch_visual_import_alerts(shared_mapping: Any) -> None:
    if getattr(shared_mapping, '_mapeiaai_import_alert_visual_patched', False):
        return

    original_guard = getattr(shared_mapping, '_render_bling_import_guard', None)
    original_confidence_flag = getattr(shared_mapping, 'confidence_flag', None)
    original_ranked_options = getattr(shared_mapping, '_ranked_source_options', None)

    def render_bling_import_guard_visual_only(*_args: Any, **_kwargs: Any) -> None:
        # Alerta agora é somente visual no farol/dropdown. Sem erro, sem aviso textual,
        # sem bloquear e sem orientar o usuário a preencher: a decisão final é manual.
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
            if _is_import_alert_field(target_name):
                labels = {str(option): _alert_next_to_ball(label) for option, label in dict(labels or {}).items()}
            return options, labels

        shared_mapping._ranked_source_options = ranked_source_options_with_visual_alert

    shared_mapping._mapeiaai_import_alert_visual_patched = True
    _audit(
        'mapping_import_alert_visual_only_installed',
        details={
            'alert_mark': ALERT_MARK,
            'visual_only': True,
            'patched_guard': callable(original_guard),
            'patched_confidence_flag': callable(original_confidence_flag),
            'patched_ranked_options': callable(original_ranked_options),
        },
    )


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
            reason = str(data.get('reason') or 'Sugestão das regras inteligentes')
            kind = str(data.get('kind') or 'rule')
        else:
            value = str(data or '')
            reason = 'Sugestão das regras inteligentes'
            kind = 'rule'
        out[field_name] = {'value': value, 'reason': reason, 'kind': kind}
    return out


def _render_suggested_summary(st, suggested: dict[str, dict[str, str]]) -> None:
    if not suggested:
        return
    st.info('💡 Alguns campos receberam sugestão das Regras e recursos inteligentes, mas continuam editáveis. Você pode deixar vazio, trocar a origem ou escrever valor fixo.')
    rows = []
    for field, data in suggested.items():
        rows.append({'Campo com sugestão': field, 'Origem/valor sugerido': _fixed_display(data.get('value', '')), 'Motivo': data.get('reason', '')})
    with st.expander('Ver sugestões das regras inteligentes', expanded=False):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(320, 80 + len(rows) * 35))


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

    def render_shared_contract_mapping_suggested(
        source: pd.DataFrame,
        target: pd.DataFrame,
        *,
        signature: str,
        mapping_state_key: str,
        engine_state_key: str,
        key_prefix: str = 'mapeiaai_shared',
        ai_enabled: bool = True,
    ) -> dict[str, str]:
        suggested = _locked_fields(st, key_prefix, target)
        if suggested:
            current = dict(st.session_state.get(mapping_state_key) or {})
            # Só pré-preenche campos realmente inexistentes no estado.
            # Se o campo já existe no mapeamento, inclusive vazio, isso é decisão do usuário/fluxo.
            for field, data in suggested.items():
                if field in current:
                    continue
                value = str(data.get('value') or '').strip()
                if value:
                    current[field] = value
            st.session_state[mapping_state_key] = current
            _render_suggested_summary(st, suggested)

        edited = original(
            source,
            target,
            signature=signature,
            mapping_state_key=mapping_state_key,
            engine_state_key=engine_state_key,
            key_prefix=key_prefix,
            ai_enabled=ai_enabled,
        )
        _audit('mapping_rule_suggestions_applied_editable', details={'suggested_fields': list(suggested.keys()), 'mapping_state_key': mapping_state_key})
        return dict(edited or {})

    shared_mapping.render_shared_contract_mapping = render_shared_contract_mapping_suggested
    shared_mapping._mapeiaai_locked_fields_runtime_patched = True
    _audit('mapping_locked_fields_runtime_installed', details={'strategy': 'rule_suggestions_respect_existing_blank_mapping'})


__all__ = ['install']