from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard_rerun import safe_rerun
from bling_app_zero.ui.protected_supplier_panel import render_protected_supplier_source_panel

RESPONSIBLE_FILE = 'bling_app_zero/ui/protected_supplier_runtime.py'
PATCH_ATTR = '_mapeiaai_protected_supplier_runtime_v1'
SOURCE_MODE_PROTECTED = 'Painel protegido com login'


def _valid_frame(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def install_protected_supplier_runtime() -> bool:
    try:
        from bling_app_zero.ui import universal_flow as flow
    except Exception as exc:
        add_audit_event('protected_supplier_runtime_import_failed', area='ORIGEM', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return False

    if getattr(flow, PATCH_ATTR, False):
        return False

    original_source_site = getattr(flow, '_render_source_site')
    original_read_source_upload = getattr(flow, '_read_source_upload')
    original_current_df = getattr(flow, '_current_df')
    original_store_df = getattr(flow, '_store_df')
    original_df_signature = getattr(flow, '_df_signature')
    original_clear_after_source = getattr(flow, '_clear_after_source')
    original_set_step = getattr(flow, '_set_step')
    original_audit = getattr(flow, '_audit')
    original_source_key = getattr(flow, 'UNIVERSAL_SOURCE_KEY')
    original_step_options = getattr(flow, 'STEP_OPTIONS')

    def patched_select_source_mode(value: str) -> None:
        st.session_state[flow.SOURCE_MODE_KEY] = value
        st.session_state.pop(original_source_key, None)
        st.session_state.pop('df_origem_unificada', None)
        st.session_state.pop('df_origem_arquivo', None)
        st.session_state.pop('df_origem_site', None)
        st.session_state.pop('df_origem_painel_protegido', None)
        original_clear_after_source()

    def patched_render_source_choice_cards() -> str:
        source_mode = str(st.session_state.get(flow.SOURCE_MODE_KEY) or '').strip()
        col_file, col_site, col_protected = st.columns(3)
        with col_file:
            if st.button('📎 Arquivo', use_container_width=True, key='mapeiaai_universal_source_file_btn'):
                patched_select_source_mode(flow.SOURCE_MODE_UPLOAD)
                safe_rerun('universal_source_file_selected')
        with col_site:
            if st.button('🌐 Site público', use_container_width=True, key='mapeiaai_universal_source_site_btn'):
                patched_select_source_mode(flow.SOURCE_MODE_SITE)
                safe_rerun('universal_source_site_selected')
        with col_protected:
            if st.button('🔐 Painel protegido', use_container_width=True, key='mapeiaai_universal_source_protected_btn'):
                patched_select_source_mode(SOURCE_MODE_PROTECTED)
                safe_rerun('universal_source_protected_selected')
        source_mode = str(st.session_state.get(flow.SOURCE_MODE_KEY) or source_mode or '').strip()
        if not source_mode:
            st.warning('Atenção: escolha Arquivo, Site público ou Painel protegido.')
        elif source_mode == SOURCE_MODE_PROTECTED:
            st.success('Origem selecionada: Painel protegido com login.')
        else:
            st.success(f'Origem selecionada: {"Arquivo" if source_mode == flow.SOURCE_MODE_UPLOAD else "Site público"}.')
        return source_mode

    def _store_source(source: pd.DataFrame, source_kind: str, audit_action: str) -> pd.DataFrame:
        previous = original_current_df(original_source_key)
        if original_df_signature(previous) not in {'none', original_df_signature(source)}:
            original_clear_after_source()
        clean = source.copy().fillna('')
        original_store_df(original_source_key, clean)
        st.session_state['df_origem_unificada'] = clean.copy().fillna('')
        if source_kind == 'arquivo':
            st.session_state['df_origem_arquivo'] = clean.copy().fillna('')
        elif source_kind == 'painel_protegido':
            st.session_state['df_origem_painel_protegido'] = clean.copy().fillna('')
            st.session_state['df_origem_arquivo'] = clean.copy().fillna('')
        st.session_state['mapeiaai_universal_source_kind'] = source_kind
        original_audit(audit_action, rows=int(len(clean)), columns=int(len(clean.columns)), source_mode=source_kind)
        return clean

    def patched_render_source_step(model: pd.DataFrame | None = None) -> pd.DataFrame | None:
        st.markdown('### 2. Origem dos dados')
        st.caption('Nesta tela o sistema apenas carrega a origem. Ele não mapeia e não monta a planilha final.')
        source_mode = patched_render_source_choice_cards()
        if source_mode == flow.SOURCE_MODE_SITE:
            source = original_source_site(model)
        elif source_mode == flow.SOURCE_MODE_UPLOAD:
            uploaded = st.file_uploader('Arquivo de origem dos dados', type=None, key='mapeiaai_universal_source_upload')
            source = original_read_source_upload(uploaded)
            if isinstance(source, pd.DataFrame):
                source = _store_source(source, 'arquivo', 'mapear_planilha_fonte_anexada')
            else:
                source = original_current_df(original_source_key)
        elif source_mode == SOURCE_MODE_PROTECTED:
            source = render_protected_supplier_source_panel()
            if isinstance(source, pd.DataFrame):
                source = _store_source(source, 'painel_protegido', 'mapear_planilha_fonte_painel_protegido_anexada')
            else:
                source = original_current_df(original_source_key)
        else:
            return None
        if not isinstance(source, pd.DataFrame):
            st.info('Carregue a origem de dados para liberar a próxima etapa.')
            return None
        st.success(f'Origem carregada: {len(source)} linha(s) x {len(source.columns)} coluna(s).')
        with st.expander('Ver origem carregada', expanded=False):
            st.dataframe(source.head(30).astype(str), use_container_width=True, height=280)
        if st.button('Continuar para opcionais ➡️', use_container_width=True, key='mapeiaai_universal_go_options'):
            original_set_step(original_step_options, 'source_confirmed')
        return source

    setattr(flow, '_select_source_mode', patched_select_source_mode)
    setattr(flow, '_render_source_choice_cards', patched_render_source_choice_cards)
    setattr(flow, '_render_source_step', patched_render_source_step)
    setattr(flow, 'SOURCE_MODE_PROTECTED', SOURCE_MODE_PROTECTED)
    setattr(flow, PATCH_ATTR, True)

    add_audit_event(
        'protected_supplier_runtime_installed',
        area='ORIGEM',
        status='OK',
        details={
            'source_mode': SOURCE_MODE_PROTECTED,
            'universal_flow_patched': True,
            'supports_generic_datatables': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['SOURCE_MODE_PROTECTED', 'install_protected_supplier_runtime']
