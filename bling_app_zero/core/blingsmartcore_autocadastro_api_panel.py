from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core import bling_autocadastro_api as autocadastro_api
from bling_app_zero.core.bling_autocadastro_upsert import upsert_product
from bling_app_zero.core.blingsmartcore_autocadastro import build_not_sent_dataframe

RESPONSIBLE_FILE = 'bling_app_zero/core/blingsmartcore_autocadastro_api_panel.py'
AUTOCADASTRO_RESULT_KEY = 'blingsmartcore_autocadastro_api_result_v2'


def _eligible_df(df_not_sent: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df_not_sent, pd.DataFrame) or df_not_sent.empty:
        return pd.DataFrame()
    if 'autocadastro_elegivel' not in df_not_sent.columns:
        return df_not_sent.copy().fillna('')
    return df_not_sent[df_not_sent['autocadastro_elegivel'].astype(str).str.upper().eq('SIM')].copy().fillna('')


def _store_result(result) -> None:
    st.session_state[AUTOCADASTRO_RESULT_KEY] = {
        'attempted': int(result.attempted),
        'created': int(result.created),
        'stock_updated': int(result.stock_updated),
        'failed': int(result.failed),
        'skipped': int(result.skipped),
        'errors': list(result.errors or ()),
    }


def _render_result() -> None:
    data = st.session_state.get(AUTOCADASTRO_RESULT_KEY)
    if not isinstance(data, dict):
        return
    attempted = int(data.get('attempted') or 0)
    created = int(data.get('created') or 0)
    stock_updated = int(data.get('stock_updated') or 0)
    failed = int(data.get('failed') or 0)
    skipped = int(data.get('skipped') or 0)
    st.markdown('### Resultado do AutoCadastro via API')
    if attempted == 0:
        st.warning('Nenhum produto foi processado no AutoCadastro.')
    elif failed == 0:
        st.success(f'AutoCadastro concluído: {created}/{attempted} produto(s) criado(s)/atualizado(s) e {stock_updated} estoque(s) atualizado(s).')
    elif created > 0:
        st.warning(f'AutoCadastro parcial: {created}/{attempted} criado(s)/atualizado(s), {stock_updated} estoque(s) atualizado(s), {failed} falha(s), {skipped} ignorado(s).')
    else:
        st.error(f'AutoCadastro não concluiu: 0/{attempted} criado(s)/atualizado(s), {failed} falha(s), {skipped} ignorado(s).')
    cols = st.columns(4)
    cols[0].metric('Processados', attempted)
    cols[1].metric('Criados/Atualizados', created)
    cols[2].metric('Estoque atualizado', stock_updated)
    cols[3].metric('Falhas', failed)
    for error in list(data.get('errors') or [])[:12]:
        st.error(str(error))


def _run_autocadastro_com_upsert(eligible: pd.DataFrame, progress_callback):
    original_create = autocadastro_api._create_product

    def _create_product_upsert(token: dict[str, Any], payload: dict[str, Any]) -> tuple[str, str]:
        product_id, error, action = upsert_product(
            token,
            payload,
            url_builder=autocadastro_api._url,
            headers_builder=autocadastro_api._headers,
            lookup_path=autocadastro_api._secret('product_lookup_path', '/produtos') or '/produtos',
            create_path=autocadastro_api._secret('product_create_path', '/produtos') or '/produtos',
            update_path=autocadastro_api._secret('product_update_path', '/produtos/{id}') or '/produtos/{id}',
            update_method=autocadastro_api._secret('product_update_method', 'PUT') or 'PUT',
            timeout=autocadastro_api.SEND_TIMEOUT,
        )
        if product_id:
            add_audit_event('blingsmartcore_autocadastro_panel_upserted', area='AUTOCADASTRO', status='OK', details={'product_id': product_id, 'action': action, 'responsible_file': RESPONSIBLE_FILE})
        return product_id, error

    autocadastro_api._create_product = _create_product_upsert
    try:
        return autocadastro_api.autocadastrar_e_atualizar_estoque(eligible, progress_callback=progress_callback)
    finally:
        autocadastro_api._create_product = original_create


def render_autocadastro_panel(download_df: pd.DataFrame, result_payload: dict[str, Any], *, key: str) -> None:
    df_not_sent = build_not_sent_dataframe(download_df, result_payload)
    if df_not_sent.empty:
        return
    eligible = _eligible_df(df_not_sent)
    csv_bytes = df_not_sent.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')

    st.markdown('### BLINGSMARTCORE AutoCadastro')
    st.warning(f'{len(df_not_sent)} produto(s) não foram confirmados no envio. {len(eligible)} elegível(is) para cadastro direto via API com upsert inteligente.')
    st.download_button(
        '⬇️ Baixar planilha dos produtos não enviados',
        data=csv_bytes,
        file_name='produtos_nao_enviados_bling_autocadastro.csv',
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'autocadastro_download_not_sent_api_{key}_{len(df_not_sent)}',
    )
    st.dataframe(df_not_sent.head(100), use_container_width=True)
    _render_result()

    if not eligible.empty:
        if st.button('Cadastrar/atualizar no Bling e atualizar estoque automaticamente', use_container_width=True, key=f'autocadastro_api_run_{key}_{len(eligible)}'):
            progress_bar = st.progress(0, text='AutoCadastro via API com upsert...')
            status_box = st.empty()

            def _progress(payload: dict[str, Any]) -> None:
                total = int(payload.get('total') or 0)
                processed = int(payload.get('processed') or 0)
                created = int(payload.get('created') or 0)
                stock_updated = int(payload.get('stock_updated') or 0)
                failed = int(payload.get('failed') or 0)
                ratio = float(payload.get('progress') or 0.0)
                text = f'AutoCadastro: {processed}/{total} · criados/atualizados {created} · estoque {stock_updated} · falhas {failed}'
                progress_bar.progress(min(100, int(ratio * 100)), text=text)
                status_box.caption(text)

            result = _run_autocadastro_com_upsert(eligible, _progress)
            _store_result(result)
            try:
                progress_bar.empty()
                status_box.empty()
            except Exception:
                pass
            add_audit_event('blingsmartcore_autocadastro_api_panel_finished', area='AUTOCADASTRO', status='OK' if result.failed == 0 else 'PARCIAL', details={'attempted': result.attempted, 'created_or_updated': result.created, 'stock_updated': result.stock_updated, 'failed': result.failed, 'upsert_enabled': True, 'responsible_file': RESPONSIBLE_FILE})
            st.rerun()


__all__ = ['render_autocadastro_panel']
