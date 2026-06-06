from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.interaction_guard import (
    activate_logout_guard,
    activate_manual_back_lock,
    clear_logout_guard,
    clear_manual_back_lock,
    disconnect_backend_token,
    locked_manual_back_target,
    logout_guard_active,
    manual_back_lock_active,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/blingfix_runtime_patches.py'
_PATCH_INSTALLED_KEY = 'blingfix_runtime_patches_installed_v1'


def _patch_oauth_callback() -> None:
    from bling_app_zero.core import bling_oauth

    original: Callable[..., Any] | None = getattr(bling_oauth, '_blingfix_original_process_oauth_callback', None)
    if original is None:
        original = bling_oauth.process_oauth_callback
        setattr(bling_oauth, '_blingfix_original_process_oauth_callback', original)

    def guarded_process_oauth_callback() -> None:
        try:
            qp = getattr(st, 'query_params', {})
            code = str(qp.get('code') or '').strip() if hasattr(qp, 'get') else ''
            error = str(qp.get('error') or '').strip() if hasattr(qp, 'get') else ''
            if code or error:
                clear_logout_guard('oauth_callback_received')
        except Exception:
            pass
        original()

    bling_oauth.process_oauth_callback = guarded_process_oauth_callback


def _patch_disconnect() -> None:
    from bling_app_zero.core import bling_oauth
    from bling_app_zero.ui import home_bling_api_flow

    original: Callable[..., Any] | None = getattr(bling_oauth, '_blingfix_original_disconnect', None)
    if original is None:
        original = bling_oauth.disconnect
        setattr(bling_oauth, '_blingfix_original_disconnect', original)

    def guarded_disconnect() -> None:
        activate_logout_guard('manual_disconnect')
        try:
            original()
        finally:
            disconnect_backend_token()
            activate_logout_guard('manual_disconnect_after_clear')
            add_audit_event('bling_disconnect_guarded_runtime', area='BLING_OAUTH', status='OK', details={'responsible_file': RESPONSIBLE_FILE})

    bling_oauth.disconnect = guarded_disconnect
    home_bling_api_flow.disconnect = guarded_disconnect


def _patch_home_wizard_navigation() -> None:
    from bling_app_zero.ui import home_wizard

    original_resolve: Callable[..., Any] | None = getattr(home_wizard, '_blingfix_original_resolve_active_step', None)
    if original_resolve is None:
        original_resolve = home_wizard._resolve_active_step
        setattr(home_wizard, '_blingfix_original_resolve_active_step', original_resolve)

    def guarded_resolve_active_step(active_step: str, *, has_model: bool, start_at_origin: bool) -> str:
        locked_target = locked_manual_back_target('')
        if locked_target:
            return locked_target
        return original_resolve(active_step, has_model=has_model, start_at_origin=start_at_origin)

    home_wizard._resolve_active_step = guarded_resolve_active_step

    def guarded_render_safe_step_nav(steps: list[str], active_step: str) -> None:
        if active_step not in steps:
            return
        plan = home_wizard._flow_plan()
        previous_step = plan.previous_step(active_step)
        next_step = plan.next_step(active_step)
        can_go_next = bool(next_step) and home_wizard._can_advance_from(active_step)
        contract = home_wizard.active_contract()
        locked = manual_back_lock_active(active_step)

        _render_persistent_process_bar(home_wizard, steps, active_step, locked=locked)

        if contract.is_api and can_go_next and not locked:
            home_wizard._go_to_step(next_step)
            add_audit_event('wizard_api_auto_next_applied', area='WIZARD', step=next_step, details={'from': active_step, 'to': next_step, 'flow_spine': plan.to_dict(), 'responsible_file': RESPONSIBLE_FILE})
            home_wizard.safe_rerun('wizard_api_auto_next', target_step=next_step)
            return

        if contract.is_api and can_go_next and locked:
            add_audit_event('wizard_api_auto_next_blocked_by_manual_back', area='WIZARD', step=active_step, status='OK', details={'active_step': active_step, 'next_step': next_step, 'responsible_file': RESPONSIBLE_FILE})

        st.markdown('---')
        col_back, col_status, col_next = st.columns([1, 1.4, 1])
        with col_back:
            if previous_step and st.button('⬅️ Voltar', use_container_width=True, key=f'wizard_local_back_{active_step}'):
                activate_manual_back_lock(active_step, previous_step)
                home_wizard._go_to_step(previous_step)
                add_audit_event('wizard_local_back_clicked', area='WIZARD', step=previous_step, details={'from': active_step, 'to': previous_step, 'state_preserved': True, 'flow_spine': plan.to_dict(), 'responsible_file': RESPONSIBLE_FILE})
                home_wizard.safe_rerun('wizard_back_clicked', target_step=previous_step)
            elif not previous_step:
                st.caption('Início do fluxo')
        with col_status:
            if next_step:
                if can_go_next:
                    if locked:
                        st.info(f'Você voltou para revisar: {_label_for_home_wizard(home_wizard, active_step)}. O avanço automático está pausado até tocar em Próximo.')
                    else:
                        st.success(f'Próxima etapa liberada: {home_wizard._label_for(next_step)}')
                else:
                    home_wizard.render_pending_notice(home_wizard._pending_message_for(active_step))
            else:
                st.success('Última etapa do fluxo.')
        with col_next:
            if next_step:
                if can_go_next:
                    if st.button(f'Próximo: {home_wizard._label_for(next_step)}', use_container_width=True, key=f'wizard_local_next_{active_step}'):
                        clear_manual_back_lock('manual_next_clicked')
                        home_wizard._go_to_step(next_step)
                        add_audit_event('wizard_local_next_clicked', area='WIZARD', step=next_step, details={'from': active_step, 'to': next_step, 'prerequisite_ok': True, 'state_preserved': True, 'flow_spine': plan.to_dict(), 'responsible_file': RESPONSIBLE_FILE})
                        home_wizard.safe_rerun('wizard_next_clicked', target_step=next_step)
                else:
                    home_wizard._render_blocked_next_state(next_step)
            else:
                st.caption('Final')

    home_wizard._render_safe_step_nav = guarded_render_safe_step_nav


def _patch_site_operation_guard() -> None:
    from bling_app_zero.ui import site_panel, site_panel_state

    original: Callable[..., Any] | None = getattr(site_panel_state, '_blingfix_original_get_site_df', None)
    if original is None:
        original = site_panel_state.get_site_df
        setattr(site_panel_state, '_blingfix_original_get_site_df', original)

    def guarded_get_site_df(operation: str):
        requested = _normalize_operation(operation)
        captured = _normalize_operation(st.session_state.get('site_capture_operation'))
        if requested and captured and requested != captured:
            add_audit_event('site_panel_ignored_df_from_other_operation', area='SITE', step='entrada', status='INFO', details={'requested_operation': requested, 'site_capture_operation': captured, 'reason': 'evitar_estoque_usar_captura_de_cadastro', 'responsible_file': RESPONSIBLE_FILE})
            return None
        return original(operation)

    site_panel_state.get_site_df = guarded_get_site_df
    site_panel.get_site_df = guarded_get_site_df


def _looks_like_product_catalog_df(df: Any) -> bool:
    try:
        columns = {str(col or '').strip().lower() for col in getattr(df, 'columns', [])}
    except Exception:
        return False
    product_markers = {'nome', 'produto', 'titulo', 'título', 'descricao', 'descrição', 'descricao_curta', 'preco', 'preço', 'marca', 'categoria', 'imagens', 'imagem', 'url', 'link'}
    stock_only = {'quantidade', 'id', 'codigo', 'código', 'gtin', 'deposito', 'depósito'}
    if columns and columns.issubset(stock_only):
        return False
    return len(columns.intersection(product_markers)) >= 2


def _forced_api_operation(download_df: Any, operation: object) -> str:
    requested = _normalize_operation(operation)
    explicit = _normalize_operation(st.session_state.get('operation') or st.session_state.get('selected_operation') or st.session_state.get('bling_operation') or st.session_state.get('flow_operation'))
    if requested == 'cadastro' or explicit == 'cadastro':
        return 'cadastro'
    if _looks_like_product_catalog_df(download_df):
        return 'cadastro'
    return requested or explicit or 'cadastro'


def _patch_api_batch_operation_guard() -> None:
    from bling_app_zero.ui import bling_api_batch_panel

    original_render: Callable[..., Any] | None = getattr(bling_api_batch_panel, '_blingfix_original_render_bling_api_batch_panel', None)
    if original_render is None:
        original_render = bling_api_batch_panel.render_bling_api_batch_panel
        setattr(bling_api_batch_panel, '_blingfix_original_render_bling_api_batch_panel', original_render)

    original_spine: Callable[..., Any] | None = getattr(bling_api_batch_panel, '_blingfix_original_spine_operation_or', None)
    if original_spine is None:
        original_spine = bling_api_batch_panel._spine_operation_or
        setattr(bling_api_batch_panel, '_blingfix_original_spine_operation_or', original_spine)

    def guarded_spine_operation_or(operation: str) -> str:
        requested = _normalize_operation(operation)
        if requested == 'cadastro':
            return 'cadastro'
        return original_spine(operation)

    def guarded_render_bling_api_batch_panel(download_df, operation: str, key: str, signature: str, rules_sig: str) -> None:
        forced = _forced_api_operation(download_df, operation)
        if forced != _normalize_operation(operation):
            add_audit_event('bling_api_batch_operation_forced_to_cadastro', area='BLING_ENVIO', status='OK', details={'original_operation': operation, 'forced_operation': forced, 'columns': [str(c) for c in getattr(download_df, 'columns', [])], 'reason': 'evitar_site_produto_ser_enviado_como_estoque_api', 'responsible_file': RESPONSIBLE_FILE})
        return original_render(download_df, forced, key, signature, rules_sig)

    bling_api_batch_panel._spine_operation_or = guarded_spine_operation_or
    bling_api_batch_panel.render_bling_api_batch_panel = guarded_render_bling_api_batch_panel


def _normalize_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'cadastro', 'produtos', 'produto', 'cadastrar', 'cadastro de produtos'}:
        return 'cadastro'
    if text in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'saldo'}:
        return 'estoque'
    if text in {'atualizacao_preco', 'atualização de preço', 'preco', 'preço'}:
        return 'atualizacao_preco'
    return text


def _render_persistent_process_bar(home_wizard_module: Any, steps: list[str], active_step: str, *, locked: bool) -> None:
    if active_step not in steps:
        return
    index = steps.index(active_step)
    total = max(1, len(steps))
    percent = int(((index + 1) / total) * 100)
    current_label = _label_for_home_wizard(home_wizard_module, active_step)

    st.markdown('''
<style>
.blingfix-progress-card{border:1px solid rgba(15,23,42,.10);background:linear-gradient(135deg,#ffffff 0%,#f8fafc 100%);border-radius:16px;padding:.72rem .82rem;margin:.55rem 0 .85rem 0;box-shadow:0 8px 22px rgba(15,23,42,.05);}
.blingfix-progress-title{font-size:.82rem;font-weight:900;color:#0f172a;margin-bottom:.22rem;}
.blingfix-progress-subtitle{font-size:.78rem;color:#475569;line-height:1.25;}
.blingfix-progress-locked{color:#9a3412;font-weight:850;}
</style>
''', unsafe_allow_html=True)
    lock_text = ' · avanço automático pausado' if locked else ''
    lock_class = ' blingfix-progress-locked' if locked else ''
    st.markdown(f'''
<div class="blingfix-progress-card">
  <div class="blingfix-progress-title">Acompanhamento do processo</div>
  <div class="blingfix-progress-subtitle{lock_class}">Etapa {index + 1} de {total} · {current_label}{lock_text}</div>
</div>
''', unsafe_allow_html=True)
    st.progress(max(1, min(100, percent)))


def _label_for_home_wizard(home_wizard_module: Any, step: str) -> str:
    try:
        return str(home_wizard_module._label_for(step))
    except Exception:
        return str(step or '')


def install_blingfix_runtime_patches() -> None:
    if st.session_state.get(_PATCH_INSTALLED_KEY):
        return
    _patch_oauth_callback()
    _patch_disconnect()
    _patch_home_wizard_navigation()
    _patch_site_operation_guard()
    _patch_api_batch_operation_guard()
    st.session_state[_PATCH_INSTALLED_KEY] = True
    add_audit_event('blingfix_runtime_patches_installed', area='APP', status='OK', details={'logout_guard_active': logout_guard_active(), 'api_operation_guard': True, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_blingfix_runtime_patches']
