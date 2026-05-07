from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.exporter import filename_for_operation, to_bling_csv_bytes
from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.pricing import apply_pricing
from bling_app_zero.core.validators import validate_final_df
from bling_app_zero.engines.estoque_engine import requested_columns_from_model
from bling_app_zero.pipelines.cadastro_pipeline import run_pipeline as run_cadastro_pipeline
from bling_app_zero.pipelines.estoque_pipeline import run_pipeline as run_estoque_pipeline
from bling_app_zero.pipelines.site_pipeline import run_pipeline as run_site_pipeline


OPERACOES = {
    'Cadastro de Produtos': 'cadastro',
    'Atualização de Estoque': 'estoque',
    'Busca Inteligente por Site': 'site',
}


def _show_contract(columns: list[str]) -> None:
    if not columns:
        return
    contract = build_contract(columns)
    with st.expander('Contrato de colunas solicitado pela planilha', expanded=True):
        st.caption('O crawler usa este contrato para buscar somente estes campos. Campo não encontrado fica vazio.')
        st.dataframe(
            pd.DataFrame([
                {
                    'Coluna solicitada': field.original,
                    'Tipo detectado': field.kind,
                    'Obrigatório': 'Sim' if field.required else 'Não',
                }
                for field in contract
            ]),
            use_container_width=True,
        )


def _show_mapping(mapping: dict[str, str]) -> None:
    if not mapping:
        return
    with st.expander('Mapeamento automático aplicado', expanded=False):
        st.dataframe(
            pd.DataFrame([
                {'Campo Bling': key, 'Coluna origem': value or '(vazio)'}
                for key, value in mapping.items()
            ]),
            use_container_width=True,
        )


def _download(df: pd.DataFrame, operation: str) -> None:
    if df is None or df.empty:
        st.warning('Ainda não há dados finais para baixar.')
        return

    errors = validate_final_df(df, operation)
    if errors:
        with st.expander('Avisos da validação final', expanded=True):
            for error in errors:
                st.warning(error)

    st.download_button(
        '⬇️ Baixar CSV final para o Bling',
        data=to_bling_csv_bytes(df),
        file_name=filename_for_operation(operation),
        mime='text/csv',
        use_container_width=True,
    )


def _preview(title: str, df: pd.DataFrame) -> None:
    st.markdown(f'#### {title}')
    if df is None or df.empty:
        st.info('Sem dados para exibir ainda.')
    else:
        st.dataframe(df.head(100), use_container_width=True)
        st.caption(f'{len(df)} linha(s) × {len(df.columns)} coluna(s)')


def render_home() -> None:
    st.title('🚀 IA Planilhas → Bling')
    st.markdown('### Plataforma inteligente de integração, captura, transformação e automação de dados para o ERP Bling')

    escolha = st.radio('O que você deseja fazer?', list(OPERACOES.keys()), horizontal=True)
    operacao = OPERACOES[escolha]
    st.session_state['tipo_operacao'] = operacao

    if operacao == 'cadastro':
        render_cadastro()
    elif operacao == 'estoque':
        render_estoque()
    elif operacao == 'site':
        render_site()


def render_cadastro() -> None:
    st.success('Motor independente de CADASTRO carregado.')

    col_a, col_b = st.columns(2)
    with col_a:
        origem = st.file_uploader('Origem dos produtos: planilha, XML ou PDF', type=['xlsx', 'xls', 'csv', 'xml', 'pdf'], key='upload_cadastro')
    with col_b:
        modelo = st.file_uploader('Modelo de cadastro do Bling (opcional)', type=['xlsx', 'xls', 'csv'], key='modelo_cadastro')

    usar_preco = st.checkbox('Aplicar calculadora de preço antes do mapeamento', value=False)

    if origem:
        df_origem = read_uploaded_file(origem)
        _preview('Preview da origem', df_origem)

        if usar_preco and not df_origem.empty:
            colunas = [str(c) for c in df_origem.columns]
            coluna_custo = st.selectbox('Coluna de custo/preço base', colunas)
            c1, c2, c3, c4 = st.columns(4)
            margem = c1.number_input('Lucro %', min_value=0.0, value=30.0, step=1.0)
            imposto = c2.number_input('Impostos %', min_value=0.0, value=0.0, step=1.0)
            taxa = c3.number_input('Taxas %', min_value=0.0, value=0.0, step=1.0)
            fixo = c4.number_input('Custo fixo R$', min_value=0.0, value=0.0, step=1.0)
            df_origem = apply_pricing(df_origem, coluna_custo, 'Preço de venda', margem, imposto, taxa, fixo)
            _preview('Origem com preço calculado', df_origem)

        if st.button('Gerar cadastro Bling', use_container_width=True):
            df_modelo = read_uploaded_file(modelo) if modelo else None
            df_final, mapping = run_cadastro_pipeline(df_origem, df_modelo)
            st.session_state['df_final_cadastro'] = df_final
            st.session_state['mapping_cadastro'] = mapping

    df_final = st.session_state.get('df_final_cadastro')
    mapping = st.session_state.get('mapping_cadastro', {})
    if isinstance(df_final, pd.DataFrame):
        _show_mapping(mapping)
        _preview('Preview final do cadastro', df_final)
        _download(df_final, 'cadastro')


def render_estoque() -> None:
    st.warning('Motor independente de ESTOQUE carregado.')
    st.caption('Este fluxo usa somente as colunas pedidas pelo modelo de estoque. Se não encontrar um campo, ele fica vazio.')

    col_a, col_b = st.columns(2)
    with col_a:
        origem = st.file_uploader('Origem dos dados de estoque', type=['xlsx', 'xls', 'csv'], key='upload_estoque_origem')
    with col_b:
        modelo = st.file_uploader('Modelo de estoque do Bling', type=['xlsx', 'xls', 'csv'], key='modelo_estoque')

    deposito = st.text_input('Nome do depósito', value='Não definido')

    if modelo:
        df_modelo_preview = read_uploaded_file(modelo)
        _show_contract([str(c) for c in df_modelo_preview.columns])

    if origem:
        df_origem = read_uploaded_file(origem)
        df_modelo = read_uploaded_file(modelo) if modelo else None
        _preview('Preview da origem de estoque', df_origem)

        if st.button('Gerar atualização de estoque', use_container_width=True):
            df_final, mapping = run_estoque_pipeline(df_origem, df_modelo, deposito=deposito)
            st.session_state['df_final_estoque'] = df_final
            st.session_state['mapping_estoque'] = mapping

    df_final = st.session_state.get('df_final_estoque')
    mapping = st.session_state.get('mapping_estoque', {})
    if isinstance(df_final, pd.DataFrame):
        _show_mapping(mapping)
        _preview('Preview final do estoque', df_final)
        _download(df_final, 'estoque')


def render_site() -> None:
    st.info('Crawler inteligente independente carregado.')
    st.caption('Tecnologia ativa: extração orientada por contrato de colunas. A planilha manda no que será buscado.')

    modo = st.radio('Modo da captura por site', ['Cadastro completo', 'Estoque orientado pelo modelo'], horizontal=True)
    operation = 'cadastro' if modo == 'Cadastro completo' else 'estoque'

    modelo = st.file_uploader(
        'Modelo Bling para refletir no resultado final (opcional no cadastro, recomendado no estoque)',
        type=['xlsx', 'xls', 'csv'],
        key='modelo_site_bling',
    )

    requested_columns = None
    df_modelo = None
    if modelo:
        df_modelo = read_uploaded_file(modelo)
        requested_columns = [str(c) for c in df_modelo.columns]
        _show_contract(requested_columns)
        if operation == 'estoque':
            requested_columns = requested_columns_from_model(df_modelo)

    deposito = ''
    if operation == 'estoque':
        deposito = st.text_input('Nome do depósito para estoque por site', value='Não definido')

    raw_urls = st.text_area('Links dos produtos/sites', height=180, key='urls_site')

    if st.button('Buscar somente colunas solicitadas e gerar Bling', use_container_width=True):
        df_site = run_site_pipeline(raw_urls, requested_columns=requested_columns)
        st.session_state['df_site_bruto'] = df_site

        if operation == 'estoque':
            df_final, mapping = run_estoque_pipeline(df_site, df_modelo, deposito=deposito)
        else:
            df_final, mapping = run_cadastro_pipeline(df_site, df_modelo)

        st.session_state['df_site_final'] = df_final
        st.session_state['mapping_site'] = mapping
        st.session_state['operation_site'] = operation

    df_site_bruto = st.session_state.get('df_site_bruto')
    if isinstance(df_site_bruto, pd.DataFrame):
        _preview('Captura do site baseada apenas no contrato', df_site_bruto)

    df_final = st.session_state.get('df_site_final')
    mapping = st.session_state.get('mapping_site', {})
    operation_state = st.session_state.get('operation_site', operation)
    if isinstance(df_final, pd.DataFrame):
        _show_mapping(mapping)
        _preview('Preview final Bling gerado pelo site', df_final)
        _download(df_final, operation_state)
