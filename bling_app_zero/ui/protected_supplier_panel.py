from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.protected_supplier_collectors import build_collector_zip, get_supplier, supplier_options

RESPONSIBLE_FILE = 'bling_app_zero/ui/protected_supplier_panel.py'
PROTECTED_UPLOAD_KEY = 'mapeiaai_protected_supplier_upload_v1'
PROTECTED_PROVIDER_KEY = 'mapeiaai_protected_supplier_provider_v1'
PROTECTED_URL_KEY = 'mapeiaai_protected_supplier_url_v1'
PROTECTED_PAGES_KEY = 'mapeiaai_protected_supplier_pages_v1'
PROTECTED_FORMAT_KEY = 'mapeiaai_protected_supplier_format_v1'


def _provider_labels() -> list[str]:
    return [f'{spec.name} ({spec.key})' for spec in supplier_options()]


def _provider_key_from_label(label: str) -> str:
    text = str(label or '')
    if '(' in text and text.endswith(')'):
        return text.rsplit('(', 1)[-1].rstrip(')').strip()
    return 'datatables_generic'


def _valid_frame(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def render_protected_supplier_source_panel() -> pd.DataFrame | None:
    st.markdown('#### 🔐 Painel protegido com login')
    st.caption('Use quando o fornecedor exige login. O coletor roda no seu computador e o MapeiaAI recebe apenas o ZIP com HTML/MHTML capturado.')

    labels = _provider_labels()
    selected_label = st.selectbox('Fornecedor / estratégia', labels, key=PROTECTED_PROVIDER_KEY)
    provider_key = _provider_key_from_label(selected_label)
    spec = get_supplier(provider_key)

    default_url = str(st.session_state.get(PROTECTED_URL_KEY) or spec.start_url or '')
    start_url = st.text_input('URL inicial do painel de produtos', value=default_url, key=PROTECTED_URL_KEY)
    pages = st.number_input('Quantidade máxima de páginas para capturar', min_value=1, max_value=500, value=int(spec.default_pages or 25), step=1, key=PROTECTED_PAGES_KEY)
    capture_format = st.selectbox('Formato da captura', ['mhtml', 'html', 'both'], index=0, key=PROTECTED_FORMAT_KEY)

    if not str(start_url or '').strip():
        st.warning('Informe a URL inicial do fornecedor protegido antes de baixar o coletor.')
        zip_bytes = b''
    else:
        zip_bytes = build_collector_zip(provider_key, start_url=start_url, pages=int(pages), capture_format=capture_format)

    st.download_button(
        '⬇️ Baixar coletor local configurado',
        data=zip_bytes,
        file_name=f'mapeiaai_coletor_{provider_key}.zip',
        mime='application/zip',
        disabled=not bool(zip_bytes),
        use_container_width=True,
        key='mapeiaai_download_protected_supplier_collector_v1',
    )

    with st.expander('Como funciona', expanded=False):
        st.markdown(
            '- O coletor abre o navegador no seu computador.\n'
            '- Você faz login normalmente no fornecedor.\n'
            '- Ele passa pelas páginas da tabela e salva HTML/MHTML.\n'
            '- Depois você anexa aqui o ZIP gerado.\n'
            '- Senha, cookies e tokens não são enviados ao MapeiaAI.'
        )

    uploaded = st.file_uploader(
        'Anexar ZIP/HTML/MHTML capturado pelo coletor',
        type=None,
        key=PROTECTED_UPLOAD_KEY,
    )
    if uploaded is None:
        st.info('Depois de rodar o coletor, anexe aqui o ZIP gerado na pasta capturas_fornecedor.')
        return None

    try:
        df = read_uploaded_file(uploaded).fillna('')
    except Exception as exc:
        st.error(f'Não consegui ler o arquivo capturado: {exc}')
        add_audit_event('protected_supplier_upload_read_failed', area='ORIGEM', status='ERRO', details={'error': str(exc)[:220], 'provider_key': provider_key, 'responsible_file': RESPONSIBLE_FILE})
        return None

    if not _valid_frame(df):
        st.warning('O ZIP/HTML/MHTML foi recebido, mas não virou uma tabela válida. Gere o diagnóstico e envie para BLINGFIX.')
        add_audit_event('protected_supplier_upload_empty', area='ORIGEM', status='AVISO', details={'provider_key': provider_key, 'file_name': str(getattr(uploaded, 'name', '') or ''), 'responsible_file': RESPONSIBLE_FILE})
        return None

    add_audit_event(
        'protected_supplier_upload_loaded',
        area='ORIGEM',
        status='OK',
        details={
            'provider_key': provider_key,
            'file_name': str(getattr(uploaded, 'name', '') or ''),
            'rows': int(len(df)),
            'columns': int(len(df.columns)),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    st.success(f'Captura protegida carregada: {len(df)} produto(s) x {len(df.columns)} coluna(s).')
    with st.expander('Prévia da captura protegida', expanded=False):
        st.dataframe(df.head(50).astype(str), use_container_width=True, height=320)
    return df.copy().fillna('')


__all__ = ['render_protected_supplier_source_panel']
