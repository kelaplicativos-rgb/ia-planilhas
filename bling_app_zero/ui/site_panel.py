from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.cadastro_panel import (
    _apply_calculated_price_aliases,
    _best_cost_column,
    _render_dual_stock_output,
    _render_manual_mapping,
    _show_first_row_preview,
    _sync_detected_discount,
)
from bling_app_zero.ui.home_shared import (
    df_signature,
    download_final,
    load_apply_pricing,
    load_estoque_pipeline,
    load_requested_columns_from_model,
    load_site_pipeline,
    preview_df,
    show_contract,
    show_mapping,
)
from bling_app_zero.ui.smart_upload import render_smart_upload_box


def _choose_site_model_df(upload) -> pd.DataFrame | None:
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    if isinstance(upload.source_df, pd.DataFrame):
        return upload.source_df
    return None


def _render_cadastro_site_same_as_planilha(df_origem: pd.DataFrame, df_modelo: pd.DataFrame | None) -> None:
    """Usa o mesmo fluxo operacional do cadastro por planilha, mudando só a origem.

    A captura por site vira apenas a origem de dados. Depois dela, a operação é cadastro:
    precificação opcional, mapeamento manual, preview final e CSV no mesmo padrão do
    cadastro por planilha.
    """
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        st.warning('A captura por site ainda não retornou dados para o cadastro.')
        return

    st.success('Origem site carregada. A partir daqui, a operação é a mesma do Cadastro de Produtos por planilha.')

    usar_preco = st.checkbox(
        'Aplicar calculadora de preço antes do mapeamento',
        value=False,
        key='site_cadastro_usar_precificacao',
    )

    if usar_preco:
        apply_pricing = load_apply_pricing()
        colunas = [str(c) for c in df_origem.columns]
        origem_signature = df_signature(df_origem)
        desconto_detectado = _sync_detected_discount(df_origem, f'site:{origem_signature}')

        coluna_custo = st.selectbox(
            'Coluna de custo/preço base',
            colunas,
            index=_best_cost_column(colunas),
            key=f'site_cadastro_coluna_custo_{origem_signature}',
        )
        _show_first_row_preview(df_origem, coluna_custo)

        if desconto_detectado > 0:
            st.info(f'Desconto/comissão detectado e aplicado como padrão: {desconto_detectado:.2f}%')

        c1, c2, c3, c4, c5 = st.columns(5)
        margem = c1.number_input(
            'Lucro desejado %',
            min_value=0.0,
            value=30.0,
            step=1.0,
            key=f'site_cadastro_margem_{origem_signature}',
        )
        imposto = c2.number_input(
            'Impostos %',
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f'site_cadastro_imposto_{origem_signature}',
        )
        taxa = c3.number_input(
            'Taxas %',
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f'site_cadastro_taxa_{origem_signature}',
        )
        desconto = c4.number_input(
            'Desconto/Comissão %',
            min_value=0.0,
            step=1.0,
            key='cadastro_desconto_comissao',
        )
        fixo = c5.number_input(
            'Custo fixo R$',
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f'site_cadastro_fixo_{origem_signature}',
        )

        df_origem = apply_pricing(
            df_origem,
            coluna_custo,
            'Preço de venda',
            margem,
            imposto,
            taxa,
            fixo,
            desconto,
        )
        df_origem = _apply_calculated_price_aliases(df_origem, 'Preço de venda')
        st.session_state['cadastro_preco_calculado_ativo'] = True
        st.session_state['df_origem_site_cadastro_precificada'] = df_origem
        preview_df('Origem site com preço calculado', df_origem)
    else:
        st.session_state['cadastro_preco_calculado_ativo'] = False
        st.session_state.pop('df_origem_site_cadastro_precificada', None)

    df_para_mapear = st.session_state.get('df_origem_site_cadastro_precificada', df_origem)
    _render_manual_mapping(df_para_mapear, df_modelo)
    _render_dual_stock_output(df_para_mapear, None)

    df_final = st.session_state.get('df_final_cadastro')
    mapping = st.session_state.get('mapping_cadastro', {})
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final do cadastro', df_final)
        download_final(df_final, 'cadastro', 'site_cadastro')


def render_site_panel() -> None:
    st.info('A busca por site muda apenas a ORIGEM. A operação continua sendo Cadastro ou Estoque conforme escolhido.')
    st.caption('Tecnologia ativa: FLASH AMPLO + extração orientada pela operação escolhida.')

    modo = st.radio('Operação que receberá a origem site', ['Cadastro de Produtos', 'Atualização de Estoque'], horizontal=True)
    operation = 'cadastro' if modo == 'Cadastro de Produtos' else 'estoque'

    upload = render_smart_upload_box(
        title='📎 Anexos da operação por site',
        operation=operation,
        key='smart_upload_site_modelo',
        allow_model=True,
        required_model=operation == 'estoque',
        accepted_types=None,
    )

    df_modelo = _choose_site_model_df(upload)
    requested_columns = None
    if isinstance(df_modelo, pd.DataFrame):
        requested_columns = [str(c) for c in df_modelo.columns]
        show_contract(requested_columns)
        if operation == 'estoque':
            requested_columns_from_model = load_requested_columns_from_model()
            requested_columns = requested_columns_from_model(df_modelo)

    deposito = ''
    if operation == 'estoque':
        deposito = st.text_input('Nome do depósito para estoque por site', value='Não definido')

    raw_urls = st.text_area('URL inicial, categoria, home ou links de produtos', height=180, key='urls_site')

    all_products = st.checkbox('FLASH AMPLO: varrer site/categoria e buscar todos os produtos encontrados', value=True)
    col_limit_a, col_limit_b = st.columns(2)
    max_pages = int(col_limit_a.number_input('Limite de páginas varridas', min_value=10, max_value=3000, value=250, step=50))
    max_products = int(col_limit_b.number_input('Limite de produtos capturados', min_value=10, max_value=10000, value=1000, step=100))

    if st.button('Buscar produtos no site', use_container_width=True):
        run_site_pipeline = load_site_pipeline()
        with st.spinner('Varrendo site, descobrindo produtos e preparando a origem da operação...'):
            df_site = run_site_pipeline(
                raw_urls,
                requested_columns=requested_columns,
                all_products=all_products,
                max_pages=max_pages,
                max_products=max_products,
                operation=operation,
            )
        st.session_state['df_site_bruto'] = df_site
        st.session_state['operation_site'] = operation

        if operation == 'estoque':
            run_estoque_pipeline = load_estoque_pipeline()
            df_final, mapping = run_estoque_pipeline(df_site, df_modelo, deposito=deposito)
            st.session_state['df_site_final'] = df_final
            st.session_state['mapping_site'] = mapping
        else:
            st.session_state.pop('df_site_final', None)
            st.session_state.pop('mapping_site', None)

    df_site_bruto = st.session_state.get('df_site_bruto')
    operation_state = st.session_state.get('operation_site', operation)

    if isinstance(df_site_bruto, pd.DataFrame):
        preview_df('Origem capturada do site', df_site_bruto)

        if operation_state == 'cadastro':
            _render_cadastro_site_same_as_planilha(df_site_bruto, df_modelo)
            return

    df_final = st.session_state.get('df_site_final')
    mapping = st.session_state.get('mapping_site', {})
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final Bling gerado pelo site', df_final)
        download_final(df_final, operation_state, 'site')
