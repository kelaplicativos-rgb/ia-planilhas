from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_safety_guard import install_preventive_operation_guard

RESPONSIBLE_FILE = 'bling_app_zero/ui/preventive_bootstrap.py'
MOBILE_CONNECTED_AUTO_ENTRY_KEY = 'mobile_connected_bling_auto_entry_done_v1'
EXPLICIT_API_SEND_KEY = 'home_bling_connected_same_flow_api_send'
FINISH_MODE_KEY = 'bling_finish_mode'
MODEL_PRESERVE_TOGGLE_KEY = 'mapeiaai_model_preserve_data_toggle_v1'
API_SESSION_KEYS = (
    'bling_connected_api_flow_active',
    'bling_connected_api_operation',
    'bling_connected_origin_kind',
    'bling_connected_next_human_step',
    'df_final_bling_api',
    'mapping_bling_api',
    'mapping_confidence_bling_api',
    'bling_api_automation_mapping_skipped',
    'bling_api_automation_rows',
    'bling_api_automation_columns',
    'bling_api_required_selector',
    'bling_api_must_run_ai_check',
    'bling_api_final_action',
)


def _plain_key(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return ''.join(ch for ch in text if ch.isalnum())


def _df_has_values(df) -> bool:
    try:
        frame = df.fillna('').astype(str)
        return bool(frame.apply(lambda col: col.str.strip().ne('').any()).any())
    except Exception:
        return False


def _key_options(df) -> list[str]:
    columns = [str(column) for column in getattr(df, 'columns', [])]
    terms = ('codigo', 'sku', 'idproduto', 'idnaloja', 'gtin', 'ean', 'referencia')
    preferred = [column for column in columns if any(term in _plain_key(column) for term in terms)]
    return list(dict.fromkeys([*preferred, *columns]))


def _mapped_targets(mapping, columns: list[str]) -> set[str]:
    data = dict(mapping or {})
    return {column for column in columns if str(data.get(column, '') or '').strip()}


def _install_auto_model_preserve_policy() -> None:
    try:
        import pandas as pd
        import bling_app_zero.ui as ui_root
        from bling_app_zero.core import final_output_engine
        from bling_app_zero.core import universal_model_upload_fast_patch as upload_patch
    except Exception as exc:
        add_audit_event('model_preserve_toggle_policy_import_failed', area='UNIVERSAL', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    enabled_key = getattr(ui_root, 'PRESERVE_MODEL_ENABLED_KEY', 'mapeiaai_preserve_model_data_enabled')
    key_column_key = getattr(ui_root, 'PRESERVE_MODEL_KEY_COLUMN_KEY', 'mapeiaai_preserve_model_data_key_column')
    original_builder = getattr(final_output_engine, '_mapeiaai_original_build_universal_output', None) or final_output_engine.build_universal_output

    def _set_preserve_state(model, enabled: bool) -> None:
        has_values = _df_has_values(model)
        if not has_values or not enabled:
            st.session_state[enabled_key] = False
            st.session_state['mapeiaai_universal_preserve_model_enabled'] = False
            st.session_state['mapeiaai_universal_preserve_model_mode'] = 'modelo_limpo'
            st.session_state['mapeiaai_universal_preserve_model_columns'] = []
            if not enabled:
                st.session_state[key_column_key] = ''
            return
        st.session_state[enabled_key] = True
        st.session_state['mapeiaai_universal_preserve_model_enabled'] = True
        st.session_state['mapeiaai_universal_preserve_model_mode'] = 'modelo_preenchido_preservado_por_toggle'
        st.session_state['mapeiaai_universal_preserve_model_columns'] = [str(col) for col in getattr(model, 'columns', [])]

    def _render_toggle(contract, mapping=None, key_prefix: str = 'mapeiaai_model', *, show_toggle: bool = True) -> None:
        has_values = _df_has_values(contract)
        if not has_values:
            _set_preserve_state(contract, False)
            st.caption('Modelo sem linhas preenchidas: usando somente estrutura, colunas e ordem.')
            return

        st.session_state.setdefault(MODEL_PRESERVE_TOGGLE_KEY, False)
        enabled = bool(st.session_state.get(MODEL_PRESERVE_TOGGLE_KEY, False))
        if show_toggle:
            enabled = bool(st.toggle('Preservar dados do modelo', key=MODEL_PRESERVE_TOGGLE_KEY, help='Desligado: limpa os dados do modelo. Ligado: mantém os dados do modelo e a origem atualiza por cima dos campos mapeados.'))
        _set_preserve_state(contract, enabled)

        if not enabled:
            st.caption('Desligado: o próximo passo usa a planilha modelo limpinha, pronta para receber os dados da origem.')
            return

        with st.expander('Preservação do modelo ativa', expanded=True):
            st.info('Todos os dados do modelo seguem preservados até a origem de dados sobrescrever, preencher ou limpar os campos mapeados.')
            options = _key_options(contract)
            if not options:
                st.error('Nao encontrei coluna de chave no modelo.')
                return
            current = str(st.session_state.get(key_column_key) or '').strip()
            index = options.index(current) if current in options else 0
            selected = st.selectbox('Chave para cruzar modelo + origem', options, index=index, key=f'{key_prefix}_preserve_model_key_column_toggle_v1')
            st.session_state[key_column_key] = str(selected)
            if mapping is not None and not str(dict(mapping or {}).get(str(selected), '') or '').strip():
                st.warning(f'Mapeie a coluna "{selected}" com a chave da origem antes de montar a saida final.')
            st.caption('Campo mapeado vindo da origem sobrescreve, preenche ou limpa. Campo nao mapeado permanece preservado.')

    def render_preserve_controls(contract, mapping=None, key_prefix: str = 'mapeiaai_model') -> None:
        if mapping is None:
            return
        _render_toggle(contract, mapping=mapping, key_prefix=key_prefix, show_toggle=False)

    def render_upload_toggle(module, model) -> None:
        st_obj = getattr(module, 'st', st)
        if not _df_has_values(model):
            _set_preserve_state(model, False)
            st_obj.caption('Modelo sem linhas preenchidas: usando somente estrutura, colunas e ordem.')
            return
        _render_toggle(model, mapping=None, key_prefix='mapeiaai_universal_model', show_toggle=True)

    def apply_preserve_by_toggle(df_source, df_model, mapping=None, builder=None):
        build = builder or original_builder
        mapped = build(df_source, df_model, mapping).copy().fillna('')
        if not _df_has_values(df_model) or not bool(st.session_state.get(MODEL_PRESERVE_TOGGLE_KEY, False)):
            st.session_state[enabled_key] = False
            return mapped

        st.session_state[enabled_key] = True
        base = df_model.copy().fillna('')
        for column in mapped.columns:
            if column not in base.columns:
                base[column] = ''
        base = base.loc[:, list(mapped.columns)].fillna('').reset_index(drop=True)
        if base.empty:
            return mapped

        key_column = str(st.session_state.get(key_column_key) or '').strip()
        if not key_column or key_column not in base.columns or key_column not in mapped.columns:
            for option in _key_options(base):
                if option in base.columns and option in mapped.columns:
                    key_column = str(option)
                    st.session_state[key_column_key] = key_column
                    break
        if not key_column:
            return base

        update_columns = _mapped_targets(mapping, list(mapped.columns))
        if not update_columns:
            return base

        index_by_key = {}
        for idx, value in enumerate(base[key_column].tolist()):
            key = _plain_key(value)
            if key and key not in index_by_key:
                index_by_key[key] = idx

        out = base.copy().fillna('')
        matched = appended = 0
        for _, row in mapped.iterrows():
            key = _plain_key(row.get(key_column, ''))
            if not key:
                continue
            if key in index_by_key:
                matched += 1
                target_row = index_by_key[key]
                for column in update_columns:
                    out.at[target_row, column] = '' if row.get(column) is None else str(row.get(column))
            else:
                new_row = {column: '' if row.get(column) is None else str(row.get(column)) for column in out.columns}
                out = pd.concat([out, pd.DataFrame([new_row], columns=list(out.columns))], ignore_index=True)
                index_by_key[key] = len(out) - 1
                appended += 1

        add_audit_event('model_preserve_by_toggle_applied', area='UNIVERSAL', status='OK', details={'matched_rows': matched, 'appended_rows': appended, 'key_column': key_column, 'responsible_file': RESPONSIBLE_FILE})
        return out

    ui_root._render_model_preserve_controls = render_preserve_controls
    ui_root._apply_model_preserve = apply_preserve_by_toggle
    final_output_engine.build_universal_output = lambda df_source, df_model, mapping=None: apply_preserve_by_toggle(df_source, df_model, mapping, original_builder)
    try:
        upload_patch._render_model_preservation_options = render_upload_toggle
    except Exception:
        pass
    add_audit_event('model_preserve_toggle_policy_installed', area='UNIVERSAL', status='OK', details={'default_clean_model': True, 'toggle_default_off': True, 'responsible_file': RESPONSIBLE_FILE})


def _disable_connection_driven_auto_entry() -> None:
    was_enabled = bool(st.session_state.get(MOBILE_CONNECTED_AUTO_ENTRY_KEY))
    st.session_state[MOBILE_CONNECTED_AUTO_ENTRY_KEY] = True
    if not was_enabled:
        add_audit_event(
            'connection_driven_auto_entry_disabled',
            area='HOME',
            step='startup',
            status='OK',
            details={'connection_only': True, 'requires_explicit_home_selection': True, 'responsible_file': RESPONSIBLE_FILE},
        )


def _clear_inactive_api_session() -> None:
    explicit_api = bool(st.session_state.get(EXPLICIT_API_SEND_KEY))
    finish_mode = str(st.session_state.get(FINISH_MODE_KEY) or '').strip().lower()
    if explicit_api or finish_mode == 'api_direct':
        return
    removed: list[str] = []
    for key in API_SESSION_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    if removed:
        add_audit_event('inactive_api_session_cleared_for_manual_flow', area='HOME', step='startup', status='OK', details={'removed_keys': removed, 'manual_mapping_preserved': True, 'responsible_file': RESPONSIBLE_FILE})


def install_preventive_bootstrap() -> None:
    _install_auto_model_preserve_policy()
    _disable_connection_driven_auto_entry()
    _clear_inactive_api_session()
    try:
        decision = install_preventive_operation_guard(st.session_state)
        if not decision.ok:
            st.warning(decision.message)
            add_audit_event('preventive_bootstrap_user_notice_rendered', area='APP', step='startup', status='AVISO', details={'reason': decision.reason, 'details': decision.details or {}, 'responsible_file': RESPONSIBLE_FILE})
    except Exception as exc:
        add_audit_event('preventive_bootstrap_failed_non_blocking', area='APP', step='startup', status='AVISO', details={'error': str(exc)[:300], 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_preventive_bootstrap']
