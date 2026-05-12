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
    hints = ('custo', 'preco de custo', 'preço de custo', 'valor custo', 'valor compra', 'preco compra', 'preço compra')
    blocked = ('idproduto', 'id produto', 'id na loja', 'id loja', 'sku', 'codigo', 'código', 'descricao', 'descrição', 'nome')
    for column in [str(column) for column in df.columns]:
        lower = column.lower()
        if any(term in lower for term in blocked):
            others.append(column)
        elif any(hint in lower for hint in hints):
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
    st.markdown('## 🏬 Atualizar Preços Multiloja')
    st.caption('Fluxo V2 independente: modelo multiloja do Bling + origem de custo + calculadora por marketplace.')

    st.markdown('### 1. Modelo multiloja do Bling')
    st.caption('Anexe a planilha exportada do Bling para vínculo/preços multiloja. Ela será a estrutura final do CSV.')
    model_upload = st.file_uploader('Planilha modelo do Bling para vínculo multiloja', type=['csv', 'xlsx', 'xls'], key='v2_multistore_model_upload')
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

    st.markdown('### 3. Origem de custo')
    st.caption('Obrigatório: anexe a planilha de cadastro/produtos que contém o Preço de custo. O modelo multiloja não deve ser usado como custo.')
    source_upload = st.file_uploader('Planilha de cadastro/produtos com Preço de custo', type=['csv', 'xlsx', 'xls'], key='v2_multistore_source_upload')
    source_df = _read(source_upload)
    if isinstance(source_df, pd.DataFrame) and not source_df.empty:
        st.success(f'Origem de custo carregada: {len(source_df)} linha(s) × {len(source_df.columns)} coluna(s).')
        st.dataframe(source_df.head(12), use_container_width=True, height=180)
    else:
        _render_alert('Para calcular Preços Multiloja, anexe a planilha de cadastro/produtos com Preço de custo.')

    cost_options = _cost_column_options(source_df)
    source_cost_column = st.selectbox('Coluna de Preço de custo na origem', cost_options, key='v2_multistore_cost_column') if cost_options else ''
    can_generate = isinstance(source_df, pd.DataFrame) and not source_df.empty and bool(source_cost_column)

    st.markdown('### 4. Calculadora')
    calculator_mode = st.radio(
        'Modo da calculadora',
        ['Lucro nominal', 'Margem de contribuição', 'Preço fixo'],
        horizontal=True,
        key='v2_multistore_calculator_mode_label',
    )
    mode_map = {
        'Lucro nominal': 'nominal_profit',
        'Margem de contribuição': 'contribution_margin',
        'Preço fixo': 'fixed_sale_price',
    }
    calculator_mode_key = mode_map[calculator_mode]

    c1, c2, c3, c4 = st.columns(4)
    marketplace_fee = c1.number_input('Taxa marketplace %', min_value=0.0, value=16.0 if channel == 'mercado_livre' else 14.0, step=0.5, key='v2_multistore_marketplace_fee')
    tax = c2.number_input('Imposto %', min_value=0.0, value=8.0, step=0.5, key='v2_multistore_tax')
    freight = c3.number_input('Frete R$', min_value=0.0, value=0.0, step=0.5, key='v2_multistore_freight')
    other_fees = c4.number_input('Outras taxas %', min_value=0.0, value=0.0, step=0.5, key='v2_multistore_other_fees')

    c5, c6, c7, c8 = st.columns(4)
    if calculator_mode_key == 'nominal_profit':
        desired_nominal_profit = c5.number_input('Lucro nominal R$', min_value=0.0, value=15.0, step=0.5, key='v2_multistore_desired_nominal_profit')
        desired_margin = 0.0
        desired_sale_price = 0.0
    elif calculator_mode_key == 'contribution_margin':
        desired_margin = c5.number_input('Margem desejada %', min_value=0.0, value=15.0, step=0.5, key='v2_multistore_desired_margin')
        desired_nominal_profit = 0.0
        desired_sale_price = 0.0
    else:
        desired_sale_price = c5.number_input('Preço fixo R$', min_value=0.0, value=0.0, step=0.5, key='v2_multistore_desired_sale_price')
        desired_nominal_profit = 0.0
        desired_margin = 0.0
    supplier_term = c6.number_input('Prazo fornecedor (dias)', min_value=0.0, value=15.0, step=1.0, key='v2_multistore_supplier_term')
    stock_turnover = c7.number_input('Giro estoque (dias)', min_value=0.0, value=30.0, step=1.0, key='v2_multistore_stock_turnover')
    promo = c8.number_input('Promo %', min_value=0.0, value=0.0, step=0.5, key='v2_multistore_promo')

    pricing_rules = {
        'calculator_mode': calculator_mode_key,
        'marketplace_fee_percent': marketplace_fee,
        'commission_percent': marketplace_fee,
        'tax_percent': tax,
        'freight_cost': freight,
        'other_sale_fees_percent': other_fees,
        'desired_nominal_profit': desired_nominal_profit,
        'desired_contribution_margin_percent': desired_margin,
        'desired_sale_price': desired_sale_price,
        'supplier_term_days': supplier_term,
        'stock_turnover_days': stock_turnover,
        'promo_discount_percent': promo,
    }
    profile = build_store_profile(channel, store_id=store_id, name=store_name, overrides={'pricing_rules': pricing_rules})

    if not can_generate:
        _render_alert('A geração fica bloqueada até carregar a origem de custo e selecionar a coluna de Preço de custo.')

    if st.button('Gerar planilha de preços multilojas', use_container_width=True, key='v2_multistore_generate', disabled=not can_generate):
        result = run_multistore_price_flow(model_df, profile, source_df, source_cost_column, pricing_rules)
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
