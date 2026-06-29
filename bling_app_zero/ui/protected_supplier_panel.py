from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.protected_supplier_collectors import build_collector_zip

RESPONSIBLE_FILE = 'bling_app_zero/ui/protected_supplier_panel.py'
PROTECTED_UPLOAD_KEY = 'mapeiaai_protected_supplier_upload_v1'
PROTECTED_URL_KEY = 'mapeiaai_protected_supplier_url_v2'
UNIVERSAL_PROVIDER_KEY = 'datatables_generic'
INTERNAL_MAX_CAPTURE_PAGES = 500


def _valid_frame(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def _read_uploaded_capture(uploaded) -> pd.DataFrame:
    from bling_app_zero.core import files as files_module
    return files_module.read_uploaded_file(uploaded).fillna('')


def render_protected_supplier_source_panel() -> pd.DataFrame | None:
    st.markdown('#### 🔐 Painel protegido com login')
    st.caption('Informe apenas o site do painel. O coletor abre o navegador no seu computador para login e captura HTML/MHTML automaticamente.')

    start_url = st.text_input(
        'Site do painel de produtos',
        value=str(st.session_state.get(PROTECTED_URL_KEY) or '').strip(),
        placeholder='https://fornecedor.com.br/admin/produtos',
        key=PROTECTED_URL_KEY,
    )

    site_ok = bool(str(start_url or '').strip())
    zip_bytes = (
        build_collector_zip(
            UNIVERSAL_PROVIDER_KEY,
            start_url=start_url,
            pages=INTERNAL_MAX_CAPTURE_PAGES,
            capture_format='mhtml',
        )
        if site_ok
        else b''
    )

    st.download_button(
        '⬇️ Baixar coletor automático',
        data=zip_bytes,
        file_name='mapeiaai_coletor_painel_protegido.zip',
        mime='application/zip',
        disabled=not site_ok,
        use_container_width=True,
        key='mapeiaai_download_protected_supplier_collector_v2',
    )

    uploaded = st.file_uploader(
        'Anexar captura gerada pelo coletor',
        type=None,
        key=PROTECTED_UPLOAD_KEY,
    )
    if uploaded is None:
        st.info('Depois de rodar o coletor, anexe aqui o ZIP gerado.')
        return None

    try:
        df = _read_uploaded_capture(uploaded)
    except Exception as exc:
        st.error(f'Não consegui ler o arquivo capturado: {exc}')
        add_audit_event(
            'protected_supplier_upload_read_failed',
            area='ORIGEM',
            status='ERRO',
            details={
                'error': str(exc)[:220],
                'provider_key': UNIVERSAL_PROVIDER_KEY,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return None

    if not _valid_frame(df):
        st.warning('O ZIP/HTML/MHTML foi recebido, mas não virou uma tabela válida. Gere o diagnóstico e envie para BLINGFIX.')
        add_audit_event(
            'protected_supplier_upload_empty',
            area='ORIGEM',
            status='AVISO',
            details={
                'provider_key': UNIVERSAL_PROVIDER_KEY,
                'file_name': str(getattr(uploaded, 'name', '') or ''),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return None

    add_audit_event(
        'protected_supplier_upload_loaded',
        area='ORIGEM',
        status='OK',
        details={
            'provider_key': UNIVERSAL_PROVIDER_KEY,
            'file_name': str(getattr(uploaded, 'name', '') or ''),
            'rows': int(len(df)),
            'columns': int(len(df.columns)),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    st.success(f'Captura carregada: {len(df)} produto(s) x {len(df.columns)} coluna(s).')
    with st.expander('Prévia da captura', expanded=False):
        st.dataframe(df.head(50).astype(str), use_container_width=True, height=320)
    return df.copy().fillna('')


__all__ = ['render_protected_supplier_source_panel']
