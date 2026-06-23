from __future__ import annotations

import streamlit as st
from bling_app_zero.core.audit import add_audit_event

PATCH_KEY = 'final_bling_operation_selector_runtime_installed_v3'
RESPONSIBLE_FILE = 'bling_app_zero/ui/final_bling_operation_selector_runtime.py'
ORIGINAL_PANEL_ATTR = '_final_bling_operation_selector_original_panel_v3'
ORIGINAL_INFER_ATTR = '_final_bling_operation_selector_original_infer_v3'


def _n(v):
    s = str(v or '').strip().lower()
    for a, b in {'ã':'a','á':'a','à':'a','â':'a','é':'e','ê':'e','í':'i','ó':'o','ô':'o','õ':'o','ú':'u','ç':'c','*':''}.items():
        s = s.replace(a, b)
    return ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in s).split())


def _cols(df):
    try:
        return {_n(c) for c in getattr(df, 'columns', [])}
    except Exception:
        return set()


def _is_stock(df):
    c = _cols(df)
    return bool({'deposito','movimentacao de estoque','tipo de lancamento'} & c) and bool({'id produto','codigo sku','codigo','sku','gtin ean'} & c)


def _set_op(op):
    for k in ('final_download_operation','df_final_download_operation','df_final_preview_operation','bling_api_operation','api_operation','bling_connected_api_operation','flow_spine_sender_operation','flow_spine_api_batch_operation','flow_spine_operation_resolved_for_api','flow_spine_operation','active_feature_operation','home_slim_flow_operation'):
        st.session_state[k] = op
    st.session_state['flow_spine_sender_destination'] = 'api_bling'
    st.session_state['flow_spine_final_destination'] = 'api_bling'
    st.session_state['home_bling_connected_same_flow_api_send'] = True


def _safe_widget_key(key_prefix, df):
    return f'{key_prefix}_final_bling_operation_select_v3_{len(getattr(df, "columns", []))}_{len(df) if hasattr(df, "__len__") else 0}'


def install_final_bling_operation_selector_runtime():
    if st.session_state.get(PATCH_KEY):
        return
    try:
        from bling_app_zero.ui import shared_final_csv as sfc
        from bling_app_zero.ui import bling_api_batch_panel as batch
    except Exception as e:
        add_audit_event('final_bling_selector_import_failed', area='BLING_API', status='AVISO', details={'error': str(e)[:180], 'responsible_file': RESPONSIBLE_FILE})
        return

    current_panel = getattr(sfc, '_render_final_bling_api_panel', None)
    current_infer = getattr(sfc, '_infer_bling_operation', lambda df: 'universal')

    original_panel = getattr(sfc, ORIGINAL_PANEL_ATTR, None)
    if original_panel is None or getattr(original_panel, '__module__', '') == __name__:
        original_panel = current_panel
        setattr(sfc, ORIGINAL_PANEL_ATTR, original_panel)

    original_infer = getattr(sfc, ORIGINAL_INFER_ATTR, None)
    if original_infer is None or getattr(original_infer, '__module__', '') == __name__:
        original_infer = current_infer
        setattr(sfc, ORIGINAL_INFER_ATTR, original_infer)

    native_batch = getattr(batch, '_blingfix_original_render_bling_api_batch_panel', batch.render_bling_api_batch_panel)
    current_batch = batch.render_bling_api_batch_panel

    def infer(df):
        return 'estoque' if _is_stock(df) else original_infer(df)

    def guarded_batch(df, op, key, sig, rules_sig):
        if str(op) == 'estoque' and _is_stock(df):
            _set_op('estoque')
            return native_batch(df, 'estoque', key, sig, rules_sig)
        return current_batch(df, op, key, sig, rules_sig)

    def panel(df, *, key_prefix):
        auto = infer(df)
        labels = ['Atualização de estoque / saldo', 'Cadastro de produtos', 'Atualização de preços']
        values = {'Atualização de estoque / saldo':'estoque', 'Cadastro de produtos':'cadastro', 'Atualização de preços':'atualizacao_preco'}
        default = 'Atualização de estoque / saldo' if auto == 'estoque' else 'Cadastro de produtos' if auto == 'cadastro' else 'Atualização de preços' if auto == 'atualizacao_preco' else 'Atualização de estoque / saldo'
        picked = st.selectbox('Escolha a operação para enviar ao Bling', labels, index=labels.index(default), key=_safe_widget_key(key_prefix, df))
        op = values[picked]
        _set_op(op)
        old_infer = sfc._infer_bling_operation
        old_batch_ref = getattr(sfc, 'render_bling_api_batch_panel', None)
        try:
            sfc._infer_bling_operation = lambda _df: op
            sfc.render_bling_api_batch_panel = guarded_batch
            if callable(original_panel) and getattr(original_panel, '__module__', '') != __name__:
                return original_panel(df, key_prefix=key_prefix)
            st.error('Painel de envio ao Bling indisponível nesta execução. Atualize a página após o deploy.')
            return None
        finally:
            sfc._infer_bling_operation = old_infer
            if old_batch_ref is not None:
                sfc.render_bling_api_batch_panel = old_batch_ref

    if callable(original_panel):
        sfc._infer_bling_operation = infer
        sfc._render_final_bling_api_panel = panel
        batch.render_bling_api_batch_panel = guarded_batch
        st.session_state[PATCH_KEY] = True
        add_audit_event('final_bling_selector_installed_v3', area='BLING_API', status='OK', details={'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_final_bling_operation_selector_runtime']
