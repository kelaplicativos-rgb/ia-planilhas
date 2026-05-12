from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.v2.bling_links import BLING_MULTISTORE_PRICE_IMPORT_URL
from bling_app_zero.v2.exporter import to_csv_bytes
from bling_app_zero.v2.price_multistore.detector import detect_multistore_model
from bling_app_zero.v2.price_multistore.flow import run_multistore_price_flow
from bling_app_zero.v2.store_profiles import build_store_profile
from bling_app_zero.v2.table_io import load_table

RESPONSIBLE_FILE = 'bling_app_zero/v2/price_multistore/ui.py'


def _read(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    try:
        return load_table(uploaded_file).fillna('')
    except Exception as exc:
        st.error(f'Não consegui ler a planilha: {exc}')
        return None


def _cost_column_options(df: pd.DataFrame | None) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    preferred = []
    others = []
    hints = ('custo', 'preco de custo', 'preço de custo', 'valor custo', 'valor compra')
    for column in [str(column) for column in df.columns]:
        lower = column.lower()
        if any(hint in lower for hint in hints):
            preferred.append(column)
        else:
            others.append(column)
    return preferred + others


def _render_alert(message: str) -> None:
    st.markdown(
        f"""
        <div style="background:#fff7ed;border:1px solid #fed7aa;color:#7c2d12;border-radius:16px;padding:.9rem 1rem;font-weight:700;">
            ⚠️ {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_bling_import_link() -> None:
    st.markdown(
        f"""
        <div style="margin-top:.75rem;background:#ecfdf5;border:1px solid #bbf7d0;color:#14532d;border-radius:16px;padding:.9rem 1rem;font-weight:700;">
            ✅ Depois de baixar o CSV limpo, clique abaixo para abrir o importador direto no Bling.
            <br>
            <a href="{BLING_MULTISTORE_PRICE_IMPORT_URL}" target="_blank" rel="noopener noreferrer" style="color:#047857;font-weight:900;text-decoration:none;">
                Abrir importador de preços multilojas no Bling ↗
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_price_multistore_v2() -> None:
    st.markdown('## Atualizar preços multilojas')
    st.caption('Fluxo V2 independente: um marketplace por vez, uma planilha modelo do Bling por vez.')

    model_upload = st.file_uploader('1. Anexe a planilha modelo do Bling para vínculo multiloja', type=['csv', 'xlsx', 'xls'], key='v2_multistore_model_upload')
    model_df = _read(model_upload)
    if isinstance(model_df, pd.DataFrame):
        detection = detect_multistore_model(model_df)
        if detection.is_multistore:
            st.success(f'{detection.message} Confiança: {detection.confidence:.0%}')
            st.dataframe(model_df.head(20), use_container_width=True, height=220)
        else:
            _render_alert(detection.message + ' Faltando: ' + ', '.join(detection.missing))
            return
    else:
        _render_alert('Anexe primeiro a planilha exportada do Bling para vínculo multiloja.')
        return

    st.markdown('### 2. Marketplace / Loja')
    channel = st.selectbox('Marketplace', ['mercado_livre', 'shopee', 'amazon', 'outro'], format_func=lambda x: x.replace('_', ' ').title(), key='v2_multistore_channel')
    store_name = st.text_input('Nome da loja no Bling', value=channel.replace('_', ' ').title(), key='v2_multistore_store_name')
    store_id = st.text_input('ID da loja no Bling, se houver', value='', key='v2_multistore_store_id')

    st.markdown('### 3. Origem do custo')
    source_upload = st.file_uploader('Anexe a planilha de custo/origem, se o custo não estiver no modelo', type=['csv', 'xlsx', 'xls'], key='v2_multistore_source_upload')
    source_df = _read(source_upload)
    cost_options = _cost_column_options(source_df) or _cost_column_options(model_df)
    source_cost_column = st.selectbox('Coluna de custo/preço base', cost_options, key='v2_multistore_cost_column') if cost_options else ''

    st.markdown('### 4. Calculadora')
    c1, c2, c3, c4, c5 = st.columns(5)
    commission = c1.number_input('Comissão %', min_value=0.0, value=16.0 if channel == 'mercado_livre' else 14.0, step=0.5, key='v2_multistore_commission')
    fixed_fee = c2.number_input('Taxa fixa R$', min_value=0.0, value=0.0, step=0.5, key='v2_multistore_fixed_fee')
    tax = c3.number_input('Imposto %', min_value=0.0, value=0.0, step=0.5, key='v2_multistore_tax')
    profit = c4.number_input('Lucro %', min_value=0.0, value=30.0, step=0.5, key='v2_multistore_profit')
    promo = c5.number_input('Promo %', min_value=0.0, value=0.0, step=0.5, key='v2_multistore_promo')

    pricing_rules = {
        'commission_percent': commission,
        'fixed_fee': fixed_fee,
        'tax_percent': tax,
        'profit_percent': profit,
        'promo_discount_percent': promo,
    }
    profile = build_store_profile(channel, store_id=store_id, name=store_name, overrides={'pricing_rules': pricing_rules})

    if st.button('Gerar planilha de preços multilojas', use_container_width=True, key='v2_multistore_generate'):
        source_for_flow = source_df if isinstance(source_df, pd.DataFrame) else model_df
        result = run_multistore_price_flow(model_df, profile, source_for_flow, source_cost_column, pricing_rules)
        st.session_state['v2_multistore_last_ok'] = result.ok
        st.session_state['v2_multistore_last_message'] = result.message
        st.session_state['v2_multistore_last_errors'] = list(result.errors)
        if result.ok:
            st.session_state['v2_multistore_result_df'] = result.payload.df.copy().fillna('')
        else:
            st.session_state.pop('v2_multistore_result_df', None)
        st.rerun()

    if st.session_state.get('v2_multistore_last_message'):
        if st.session_state.get('v2_multistore_last_ok'):
            st.success(st.session_state['v2_multistore_last_message'])
        else:
            _render_alert(st.session_state['v2_multistore_last_message'])
            for error in st.session_state.get('v2_multistore_last_errors', []):
                st.caption(f'• {error}')

    result_df = st.session_state.get('v2_multistore_result_df')
    if isinstance(result_df, pd.DataFrame) and not result_df.empty:
        st.markdown('### 5. Preview final')
        preview_cols = [column for column in ['IdProduto', 'ID na Loja', 'Preço', 'Preco', 'Preço Promocional', 'Preco Promocional', 'Nome da Loja'] if column in result_df.columns]
        st.dataframe(result_df[preview_cols].head(80) if preview_cols else result_df.head(80), use_container_width=True, height=340)
        st.download_button(
            'Baixar CSV para Importar e Atualizar Vínculo Produtos Multilojas',
            data=to_csv_bytes(result_df),
            file_name='bling_precos_multilojas.csv',
            mime='text/csv; charset=utf-8',
            use_container_width=True,
            key='v2_multistore_download',
        )
        _render_bling_import_link()


__all__ = ['render_price_multistore_v2']
