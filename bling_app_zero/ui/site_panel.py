from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.cadastro_tools import apply_pricing_ui, build_manual_mapping_result, cadastro_model
from bling_app_zero.ui.home_shared import (
    download_final,
    load_estoque_pipeline,
    load_requested_columns_from_model,
    load_site_pipeline,
    preview_df,
    show_contract,
    show_mapping,
)
from bling_app_zero.ui.model_upload import render_model_upload_box


def _unique_columns(columns: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for column in columns:
        text = str(column or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _columns_from_df(df: pd.DataFrame | None) -> list[str]:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return [str(c) for c in df.columns]
    return []


def _choose_site_model_df(upload, operation: str) -> pd.DataFrame | None:
    if operation == 'estoque' and isinstance(upload.estoque_model_df, pd.DataFrame):
        return upload.estoque_model_df
    if operation == 'cadastro' and isinstance(upload.cadastro_model_df, pd.DataFrame):
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    return None


def _choose_site_cadastro_model_df(upload) -> pd.DataFrame | None:
    if isinstance(upload.cadastro_model_df, pd.DataFrame):
        return upload.cadastro_model_df
    if isinstance(upload.model_df, pd.DataFrame):
        return upload.model_df
    return None


def _choose_site_estoque_model_df(upload) -> pd.DataFrame | None:
    if isinstance(upload.estoque_model_df, pd.DataFrame):
        return upload.estoque_model_df
    return None


def _requested_columns_for_site_capture(
    operation: str,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo_operacao: pd.DataFrame | None,
) -> list[str] | None:
    if operation == 'cadastro':
        cadastro_columns = _columns_from_df(df_modelo_cadastro)
        estoque_columns = _columns_from_df(df_modelo_estoque)
        merged = _unique_columns(cadastro_columns + estoque_columns)
        return merged or None
    return _columns_from_df(df_modelo_operacao) or None


def _render_site_cadastro_stock_output(df_source: pd.DataFrame, df_modelo_estoque: pd.DataFrame | None) -> None:
    st.markdown('#### Gerar também atualização de estoque')
    gerar_estoque = st.checkbox(
        'Gerar CSV de atualização de estoque usando esta mesma origem site',
        value=False,
        key='site_cadastro_gerar_estoque_mesma_origem',
    )
    if not gerar_estoque:
        st.session_state.pop('df_final_estoque_from_site_cadastro', None)
        st.session_state.pop('mapping_estoque_from_site_cadastro', None)
        return

    deposito = st.text_input(
        'Nome do depósito para o CSV de estoque',
        value='Não definido',
        key='site_cadastro_deposito_estoque_mesma_origem',
    )
    run_estoque_pipeline = load_estoque_pipeline()
    df_final_estoque, mapping_estoque = run_estoque_pipeline(df_source, df_modelo_estoque, deposito=deposito)
    st.session_state['df_final_estoque_from_site_cadastro'] = df_final_estoque
    st.session_state['mapping_estoque_from_site_cadastro'] = mapping_estoque

    show_mapping(mapping_estoque)
    preview_df('Preview final da atualização de estoque', df_final_estoque)
    download_final(df_final_estoque, 'estoque', 'estoque_from_site_cadastro')


def _render_cadastro_site_same_as_planilha(
    df_origem: pd.DataFrame,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
) -> None:
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
        df_origem = apply_pricing_ui(
            df_origem=df_origem,
            key_prefix='site_cadastro',
            preview_title='Origem site com preço calculado',
        )
        st.session_state['cadastro_preco_calculado_ativo'] = True
        st.session_state['df_origem_site_cadastro_precificada'] = df_origem
    else:
        st.session_state['cadastro_preco_calculado_ativo'] = False
        st.session_state.pop('df_origem_site_cadastro_precificada', None)

    df_para_mapear = st.session_state.get('df_origem_site_cadastro_precificada', df_origem)
    model = cadastro_model(df_modelo_cadastro)
    df_final, mapping = build_manual_mapping_result(
        df_source=df_para_mapear,
        model=model,
        mapping_key_prefix='site_cadastro_manual_mapping',
        title='#### 2. Correlacionar colunas',
        caption='Confira as sugestões e ajuste manualmente antes de gerar o preview final.',
        force_price=True,
    )
    st.session_state['df_final_cadastro'] = df_final
    st.session_state['mapping_cadastro'] = mapping

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Atualizar preview final do cadastro', use_container_width=True, key='site_cadastro_atualizar_preview'):
            st.session_state['df_final_cadastro'] = df_final
            st.session_state['mapping_cadastro'] = mapping
            st.rerun()
    with col_b:
        if st.button('Limpar correlação deste cadastro', use_container_width=True, key='site_cadastro_limpar_correlacao'):
            st.session_state.pop('df_final_cadastro', None)
            st.session_state.pop('mapping_cadastro', None)
            st.rerun()

    show_mapping(mapping)
    preview_df('Preview final do cadastro', df_final)
    download_final(df_final, 'cadastro', 'site_cadastro')

    _render_site_cadastro_stock_output(df_para_mapear, df_modelo_estoque)


def render_site_panel() -> None:
    st.info('A busca por site muda apenas a ORIGEM. A operação continua sendo Cadastro ou Estoque conforme escolhido.')
    st.caption('Tecnologia ativa: FLASH AMPLO + extração orientada pela operação escolhida.')

    modo = st.radio('Operação que receberá a origem site', ['Cadastro de Produtos', 'Atualização de Estoque'], horizontal=True)
    operation = 'cadastro' if modo == 'Cadastro de Produtos' else 'estoque'

    upload = render_model_upload_box(
        title='📎 Planilhas modelo Bling',
        operation=operation,
        key='model_upload_site',
        required_model=operation == 'estoque',
    )

    df_modelo_cadastro = _choose_site_cadastro_model_df(upload)
    df_modelo_estoque = _choose_site_estoque_model_df(upload)
    df_modelo = _choose_site_model_df(upload, operation)

    requested_columns = _requested_columns_for_site_capture(
        operation=operation,
        df_modelo_cadastro=df_modelo_cadastro,
        df_modelo_estoque=df_modelo_estoque,
        df_modelo_operacao=df_modelo,
    )

    if requested_columns:
        show_contract(requested_columns)
        if operation == 'estoque' and isinstance(df_modelo, pd.DataFrame):
            requested_columns_from_model = load_requested_columns_from_model()
            requested_columns = requested_columns_from_model(df_modelo)

    if operation == 'cadastro' and isinstance(df_modelo_estoque, pd.DataFrame):
        with st.expander('Modelo de estoque também anexado', expanded=False):
            st.caption('Esse modelo será usado para gerar também o CSV final de atualização de estoque a partir da mesma origem site.')
            st.dataframe(df_modelo_estoque.head(20), use_container_width=True, height=220)

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
            _render_cadastro_site_same_as_planilha(df_site_bruto, df_modelo_cadastro, df_modelo_estoque)
            return

    df_final = st.session_state.get('df_site_final')
    mapping = st.session_state.get('mapping_site', {})
    if isinstance(df_final, pd.DataFrame):
        show_mapping(mapping)
        preview_df('Preview final Bling gerado pelo site', df_final)
        download_final(df_final, operation_state, 'site')
