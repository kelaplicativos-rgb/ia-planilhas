from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_smart_rules_autonomy_runtime.py'
PATCH_ATTR = '_mapeiaai_smart_rules_autonomy_runtime_v1'
LOCKED_MAPPING_FIELDS_KEY = 'mapeiaai_locked_mapping_fields_v1'
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'
GOLD_MARK = '🟠'


def _audit(event: str, **details: object) -> None:
    try:
        add_audit_event(event, area='MAPEAMENTO', status='OK', details={'responsible_file': RESPONSIBLE_FILE, **details})
    except Exception:
        pass


def _plain(value: object) -> str:
    return '' if value is None else str(value).strip()


def _is_fixed(value: object) -> bool:
    return str(value or '').startswith(FIXED_VALUE_PREFIX)


def _fixed_display(value: object) -> str:
    text = str(value or '')
    if text.startswith(FIXED_VALUE_PREFIX):
        return 'FIXO: ' + text[len(FIXED_VALUE_PREFIX):].strip()
    return _plain(value)


def _smart_fields(st_module: Any, key_prefix: str | None = None) -> dict[str, dict[str, str]]:
    raw: object = {}
    if key_prefix:
        raw = st_module.session_state.get(f'{key_prefix}_locked_mapping_fields_v1') or {}
    if not raw:
        raw = st_module.session_state.get(LOCKED_MAPPING_FIELDS_KEY) or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for field, data in raw.items():
        field_name = str(field)
        if isinstance(data, dict):
            value = _plain(data.get('value'))
            reason = _plain(data.get('reason')) or 'Regra inteligente'
            kind = _plain(data.get('kind')) or 'rule'
        else:
            value = _plain(data)
            reason = 'Regra inteligente'
            kind = 'rule'
        if value:
            out[field_name] = {'value': value, 'reason': reason, 'kind': kind}
    return out


def _smart_for_target(st_module: Any, target_name: str) -> dict[str, str] | None:
    fields = _smart_fields(st_module)
    item = fields.get(str(target_name))
    if isinstance(item, dict) and _plain(item.get('value')):
        return item
    return None


def _smart_label(target_name: str, value: str, reason: str) -> str:
    display = _fixed_display(value) or '(vazio)'
    reason_text = f' · {reason}' if reason else ''
    return f'{GOLD_MARK} Regra inteligente: {display}{reason_text}'


def _same_words(sm: Any, left: object, right: object) -> bool:
    func = getattr(sm, '_same_words_case_insensitive', None)
    if callable(func):
        try:
            return bool(func(left, right))
        except Exception:
            pass
    return str(left or '').strip().casefold() == str(right or '').strip().casefold()


def _origin_reference_fixed_value(sm: Any, value: object) -> bool:
    if not _is_fixed(value):
        return False
    decoder = getattr(sm, 'decode_fixed_value', None)
    try:
        fixed = str(decoder(value) if callable(decoder) else str(value)[len(FIXED_VALUE_PREFIX):]).strip().casefold()
    except Exception:
        fixed = ''
    return bool(fixed.startswith('origem::') or fixed.startswith('origem:'))


def _insert_after_manual(sm: Any, options: list[str], smart_value: str) -> list[str]:
    empty = str(getattr(sm, 'EMPTY_OPTION', '(deixar vazio)'))
    write = str(getattr(sm, 'WRITE_OPTION', '✍️ escrever valor fixo/manual'))
    clean: list[str] = []
    seen: set[str] = set()
    for option in [empty, write, smart_value] + list(options or []):
        text = str(option)
        if text not in seen:
            clean.append(text)
            seen.add(text)
    return clean


def _render_smart_summary(st_module: Any, fields: dict[str, dict[str, str]]) -> None:
    if not fields:
        return
    rows = []
    for field, data in fields.items():
        rows.append({'Campo do modelo': field, 'Opção dourada sugerida': _fixed_display(data.get('value')), 'Motivo': data.get('reason', 'Regra inteligente')})
    st_module.info(f'{GOLD_MARK} Campos sugeridos pelas Regras e recursos inteligentes aparecem como opção dourada no dropdown. Você pode manter a sugestão ou escolher qualquer outro campo.')
    with st_module.expander('Ver sugestões douradas das regras inteligentes', expanded=False):
        st_module.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(360, 80 + len(rows) * 35))


def install_mapping_smart_rules_autonomy_runtime() -> bool:
    try:
        from bling_app_zero.ui import shared_mapping as sm
    except Exception as exc:
        _audit('mapping_smart_rules_autonomy_import_failed', error=str(exc)[:220])
        return False

    if getattr(sm, PATCH_ATTR, False):
        return False

    original_render = sm.render_shared_contract_mapping
    original_ranked = sm._ranked_source_options
    original_auto = sm._auto_bind_exact_green_matches
    original_initial = sm._initial_select_value
    original_confidence = sm.confidence_flag

    def ranked_with_gold_rule(
        target_name: str,
        current_value: str,
        source_columns: list[str],
        suggestions_index: dict[str, dict[str, Any]],
        source_profiles: dict[str, dict[str, float]] | None = None,
    ) -> tuple[list[str], dict[str, str]]:
        options, labels = original_ranked(target_name, current_value, source_columns, suggestions_index, source_profiles)
        options = [str(option) for option in list(options or [])]
        labels = dict(labels or {})
        item = _smart_for_target(sm.st, target_name)
        if item:
            smart_value = _plain(item.get('value'))
            reason = _plain(item.get('reason'))
            if smart_value:
                options = _insert_after_manual(sm, options, smart_value)
                if not _same_words(sm, target_name, smart_value):
                    labels[smart_value] = _smart_label(target_name, smart_value, reason)
        return options, labels

    def auto_bind_green_then_gold(current: dict[str, str], target_columns: list[str], source_columns: list[str]) -> tuple[dict[str, str], int]:
        updated, green_count = original_auto(current, target_columns, source_columns)
        fields = _smart_fields(sm.st)
        applied_gold = 0
        source_lookup = {tuple(getattr(sm, '_word_tuple')(source)): source for source in source_columns if tuple(getattr(sm, '_word_tuple')(source))}
        for target in list(target_columns or []):
            target_name = str(target)
            # Verde idêntico tem prioridade absoluta.
            if source_lookup.get(tuple(getattr(sm, '_word_tuple')(target_name))):
                continue
            item = fields.get(target_name)
            if not item:
                continue
            smart_value = _plain(item.get('value'))
            if not smart_value:
                continue
            current_value = _plain(updated.get(target_name))
            if current_value == smart_value:
                continue
            if _is_fixed(current_value) and not _origin_reference_fixed_value(sm, current_value):
                continue
            updated[target_name] = smart_value
            applied_gold += 1
        return updated, int(green_count or 0) + applied_gold

    def initial_select_value_smart(current_value: str, source_options: list[str]) -> str:
        if str(current_value or '') in list(source_options or []):
            return str(current_value or '')
        return original_initial(current_value, source_options)

    def confidence_flag_gold(target: str, source_column: str, source: pd.DataFrame) -> str:
        item = _smart_for_target(sm.st, target)
        if item and _plain(item.get('value')) == _plain(source_column) and not _same_words(sm, target, source_column):
            return f'{GOLD_MARK} regra inteligente'
        return original_confidence(target, source_column, source)

    def render_mapping_with_gold_rules(*args: Any, **kwargs: Any):
        key_prefix = str(kwargs.get('key_prefix') or 'mapeiaai_shared')
        fields = _smart_fields(sm.st, key_prefix)
        if fields:
            _render_smart_summary(sm.st, fields)
        return original_render(*args, **kwargs)

    sm._ranked_source_options = ranked_with_gold_rule
    sm._auto_bind_exact_green_matches = auto_bind_green_then_gold
    sm._initial_select_value = initial_select_value_smart
    sm.confidence_flag = confidence_flag_gold
    sm.render_shared_contract_mapping = render_mapping_with_gold_rules
    setattr(sm, PATCH_ATTR, True)
    _audit('mapping_smart_rules_autonomy_runtime_installed', gold_rule_option=True, user_can_override=True, auto_green_falls_back_to_gold=True)
    return True


__all__ = ['install_mapping_smart_rules_autonomy_runtime']
