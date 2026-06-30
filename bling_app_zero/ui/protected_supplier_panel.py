from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.android_collector_link import android_collector_apk_source, android_collector_apk_url
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.mobile_protected_capture import capture_url_on_mobile
from bling_app_zero.core.protected_supplier_contract_collectors import build_contract_collector_zip
from bling_app_zero.core.source_contract_enrichment import enrich_source_with_requested_columns
from bling_app_zero.engines.fast_site_scraper.constants import DISCOVERY_BUDGET_SECONDS, SAFE_CAPTURE_MAX_DEPTH, SAFE_CAPTURE_MAX_PAGES, SAFE_CAPTURE_MAX_PRODUCTS

RESPONSIBLE_FILE = 'bling_app_zero/ui/protected_supplier_panel.py'
PROTECTED_UPLOAD_KEY = 'mapeiaai_protected_supplier_upload_v1'
PROTECTED_URL_KEY = 'mapeiaai_protected_supplier_url_v2'
PROTECTED_MOBILE_DF_KEY = 'mapeiaai_protected_mobile_capture_df_v1'
PROTECTED_MOBILE_MESSAGE_KEY = 'mapeiaai_protected_mobile_capture_message_v1'
UNIVERSAL_PROVIDER_KEY = 'datatables_generic'
INTERNAL_MAX_CAPTURE_PAGES = 500
PUBLIC_ENGINE_FALLBACK_STATUSES = {'blocked_direct_capture', 'http_error', 'empty', 'network_error', 'error'}
MODEL_STATE_KEYS = ('mapeiaai_universal_model_df', 'home_modelo_universal_df', 'df_modelo_universal', 'modelo_universal_df')


def _valid_frame(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def _read_uploaded_capture(uploaded) -> pd.DataFrame:
    from bling_app_zero.core import files as files_module
    return files_module.read_uploaded_file(uploaded).fillna('')


def _current_model_df() -> pd.DataFrame | None:
    for key in MODEL_STATE_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and len(value.columns):
            return value.copy().fillna('')
    return None


def _model_columns(model: pd.DataFrame | None) -> list[str]:
    if not isinstance(model, pd.DataFrame):
        return []
    return [str(column).strip() for column in model.columns if str(column).strip()]


def _requested_columns() -> list[str]:
    return _model_columns(_current_model_df())


def _remember_public_site_url(start_url: str) -> None:
    clean_url = str(start_url or '').strip()
    if not clean_url:
        return
    for key in ('site_capture_raw_urls', 'site_capture_raw_urls_universal', 'urls_site_universal'):
        st.session_state[key] = clean_url


def _try_public_site_engine(start_url: str, reason: str) -> pd.DataFrame | None:
    clean_url = str(start_url or '').strip()
    if not clean_url:
        return None
    model = _current_model_df()
    requested_columns = _model_columns(model)
    if not requested_columns:
        add_audit_event(
            'protected_supplier_public_engine_fallback_missing_model',
            area='ORIGEM',
            status='AVISO',
            details={'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
        )
        return None

    _remember_public_site_url(clean_url)
    add_audit_event(
        'protected_supplier_public_engine_fallback_started',
        area='ORIGEM',
        status='OK',
        details={'reason': reason, 'url_host': clean_url.split('/')[2] if '://' in clean_url else clean_url[:80], 'requested_columns': len(requested_columns), 'responsible_file': RESPONSIBLE_FILE},
    )
    try:
        from bling_app_zero.ui.site_panel_capture import run_site_capture
        from bling_app_zero.ui.site_panel_state import UNIVERSAL_OPERATION, get_site_df

        deep_options = {
            'enabled': True,
            'max_pages': SAFE_CAPTURE_MAX_PAGES,
            'max_products': SAFE_CAPTURE_MAX_PRODUCTS,
            'max_depth': SAFE_CAPTURE_MAX_DEPTH,
            'scan_total_ui': True,
            'stock_balance_only': False,
            'stock_full_site_scan': False,
            'skip_predeep_discovery': False,
            'site_api_capture_policy': 'public_full_scan_from_mobile_fallback',
            'budget_seconds': DISCOVERY_BUDGET_SECONDS,
        }
        st.info('Captura direta bloqueada. Testando automaticamente a busca pública inteligente do MapeiaAI...')
        run_site_capture(
            operation=UNIVERSAL_OPERATION,
            raw_urls=clean_url,
            requested_columns=requested_columns,
            df_modelo_cadastro=model,
            df_modelo_estoque=None,
            df_modelo=model,
            deep_options=deep_options,
        )
        df_site = get_site_df(UNIVERSAL_OPERATION)
        if _valid_frame(df_site):
            add_audit_event(
                'protected_supplier_public_engine_fallback_loaded',
                area='ORIGEM',
                status='OK',
                details={'rows': int(len(df_site)), 'columns': int(len(df_site.columns)), 'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
            )
            return df_site.copy().fillna('')
    except Exception as exc:
        add_audit_event(
            'protected_supplier_public_engine_fallback_failed',
            area='ORIGEM',
            status='ERRO',
            details={'error': str(exc)[:220], 'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
        )
    return None


def _render_collector_download_links(start_url: str, site_ok: bool) -> None:
    android_url = android_collector_apk_url()
    android_source = android_collector_apk_source()
    requested_columns = _requested_columns()
    with st.expander('🔗 Leitores automáticos para baixar', expanded=False):
        st.link_button('📲 Baixar coletor Android (APK)', android_url, use_container_width=True)
        desktop_zip = (
            build_contract_collector_zip(
                UNIVERSAL_PROVIDER_KEY,
                start_url=start_url,
                pages=INTERNAL_MAX_CAPTURE_PAGES,
                capture_format='mhtml',
                requested_columns=requested_columns,
            )
            if site_ok
            else b''
        )
        st.download_button(
            '💻 Baixar coletor para computador',
            data=desktop_zip,
            file_name='mapeiaai_coletor_painel_protegido.zip',
            mime='application/zip',
            disabled=not site_ok,
            use_container_width=True,
            key='mapeiaai_download_protected_supplier_collector_v4_contract_links',
        )
        st.caption('Android usa APK. Computador usa ZIP. O MapeiaAI cruza a captura com todas as colunas do modelo anexado.')
    add_audit_event(
        'protected_supplier_collector_links_grouped_rendered',
        area='ORIGEM',
        status='INFO',
        details={'android_source': android_source, 'site_ok': site_ok, 'requested_columns': len(requested_columns), 'responsible_file': RESPONSIBLE_FILE},
    )


def _return_loaded_capture(df: pd.DataFrame, *, source: str, file_name: str = '') -> pd.DataFrame:
    requested_columns = _requested_columns()
    clean = df.copy().fillna('').astype(str)
    if requested_columns:
        clean = enrich_source_with_requested_columns(clean, requested_columns, source=source)
    add_audit_event(
        'protected_supplier_upload_loaded' if source == 'upload' else 'protected_supplier_mobile_capture_loaded',
        area='ORIGEM',
        status='OK',
        details={'provider_key': UNIVERSAL_PROVIDER_KEY, 'file_name': file_name, 'rows': int(len(clean)), 'columns': int(len(clean.columns)), 'source': source, 'requested_columns': len(requested_columns), 'contract_enrichment_applied': bool(requested_columns), 'responsible_file': RESPONSIBLE_FILE},
    )
    st.success(f'Captura carregada: {len(clean)} produto(s) x {len(clean.columns)} coluna(s).')
    with st.expander('Prévia da captura', expanded=False):
        st.dataframe(clean.head(50).astype(str), use_container_width=True, height=320)
    return clean


def render_protected_supplier_source_panel() -> pd.DataFrame | None:
    st.markdown('#### 🔐 Painel protegido com login')
    st.caption('Informe apenas o site. Use “Coletar no sistema” ou baixe um dos leitores automáticos.')

    start_url = st.text_input('Site do painel de produtos', value=str(st.session_state.get(PROTECTED_URL_KEY) or '').strip(), placeholder='https://fornecedor.com.br/admin/produtos', key=PROTECTED_URL_KEY)
    site_ok = bool(str(start_url or '').strip())

    if st.button('📱 Coletar no sistema', disabled=not site_ok, use_container_width=True, key='mapeiaai_mobile_protected_capture_btn_v1'):
        st.session_state.pop(PROTECTED_MOBILE_DF_KEY, None)
        with st.spinner('Capturando dentro do sistema...'):
            result = capture_url_on_mobile(start_url, max_pages=INTERNAL_MAX_CAPTURE_PAGES)
        st.session_state[PROTECTED_MOBILE_MESSAGE_KEY] = result.message
        if result.ok:
            st.session_state[PROTECTED_MOBILE_DF_KEY] = result.df.copy().fillna('')
            st.success(result.message)
        elif str(result.status) in PUBLIC_ENGINE_FALLBACK_STATUSES or bool(getattr(result, 'should_try_public_engine', False)):
            st.warning(result.message)
            fallback_df = _try_public_site_engine(start_url, str(result.status))
            if _valid_frame(fallback_df):
                st.session_state[PROTECTED_MOBILE_DF_KEY] = fallback_df.copy().fillna('')
                st.success('Busca pública inteligente concluída automaticamente.')
            else:
                st.warning('Não consegui concluir automaticamente. O link já ficou preparado no modo Site público; use um dos leitores automáticos se necessário.')
        else:
            st.warning(result.message)
        if not result.ok:
            add_audit_event('protected_supplier_mobile_capture_not_loaded', area='ORIGEM', status='AVISO', details={'status': result.status, 'message': result.message, 'details': result.details, 'responsible_file': RESPONSIBLE_FILE})

    mobile_df = st.session_state.get(PROTECTED_MOBILE_DF_KEY)
    if _valid_frame(mobile_df):
        return _return_loaded_capture(mobile_df, source='mobile')

    last_message = str(st.session_state.get(PROTECTED_MOBILE_MESSAGE_KEY) or '').strip()
    if last_message:
        st.caption(last_message)

    _render_collector_download_links(start_url, site_ok)

    uploaded = st.file_uploader('Anexar captura gerada pelo coletor', type=None, key=PROTECTED_UPLOAD_KEY)
    if uploaded is None:
        st.info('No celular, tente primeiro “Coletar no sistema”. Se precisar, baixe o coletor Android em APK nos links acima.')
        return None

    try:
        df = _read_uploaded_capture(uploaded)
    except Exception as exc:
        st.error(f'Não consegui ler o arquivo capturado: {exc}')
        add_audit_event('protected_supplier_upload_read_failed', area='ORIGEM', status='ERRO', details={'error': str(exc)[:220], 'provider_key': UNIVERSAL_PROVIDER_KEY, 'responsible_file': RESPONSIBLE_FILE})
        return None

    if not _valid_frame(df):
        st.warning('O ZIP/HTML/MHTML foi recebido, mas não virou uma tabela válida. Gere o diagnóstico e envie para BLINGFIX.')
        add_audit_event('protected_supplier_upload_empty', area='ORIGEM', status='AVISO', details={'provider_key': UNIVERSAL_PROVIDER_KEY, 'file_name': str(getattr(uploaded, 'name', '') or ''), 'responsible_file': RESPONSIBLE_FILE})
        return None
    return _return_loaded_capture(df, source='upload', file_name=str(getattr(uploaded, 'name', '') or ''))


__all__ = ['render_protected_supplier_source_panel']
