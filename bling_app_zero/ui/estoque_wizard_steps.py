from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_models import home_estoque_model_loaded, render_estoque_model_contract, select_estoque_model
from bling_app_zero.ui.estoque_outputs import (
    build_stock_outputs,
    build_stock_outputs_from_dataframe,
    render_stock_downloads,
    render_stock_preview,
)
from bling_app_zero.ui.estoque_sources import get_estoque_site_source, render_estoque_upload, source_files_from_upload
from bling_app_zero.ui.home_models import get_home_estoque_model
from bling_app_zero.ui.home_shared import df_signature
from bling_app_zero.ui.smart_upload import SmartUploadResult

ESTOQUE_SOURCE_SIGNATURE_KEY = 'estoque_source_signature_atual'
ESTOQUE_UPLOAD_KEY = 'estoque_wizard_upload'
ESTOQUE_ORIGEM_SITE_KEY = 'estoque_wizard_df_origem_site'
ESTOQUE_MODELO_KEY = 'estoque_wizard_df_modelo'
ESTOQUE_DEPOSITO_KEY = 'estoque_nome_deposito'
ESTOQUE_DEPOSITO_SIGNATURE_KEY = 'estoque_deposito_signature_atual'
BLING_IMPORTADOR_ESTOQUE_URL = 'https://www.bling.com.br/importador.saldos.estoque.php'


def _valid_model(df_modelo: pd.DataFrame | None) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def _deposito_value() -> str:
    return str(st.session_state.get(ESTOQUE_DEPOSITO_KEY) or '').strip()


def _valid_deposito() -> bool:
    return bool(_deposito_value())


def _is_site_origin() -> bool:
    return str(st.session_state.get('home_slim_flow_origin') or st.session_state.get('origem_final') or '').strip().lower() == 'site'


def _empty_upload_result() -> SmartUploadResult:
    return SmartUploadResult(
        source_file=None,
        source_df=None,
        model_file=None,
        model_df=get_home_estoque_model(),
        cadastro_model_file=None,
        cadastro_model_df=None,
        estoque_model_file=None,
        estoque_model_df=get_home_estoque_model(),
        attachments=[],
        ignored_files=[],
    )


def _current_source_signature(df_origem_site: pd.DataFrame | None, upload) -> str:
    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        return 'site:' + df_signature(df_origem_site)
    files = source_files_from_upload(upload)
    names = [str(getattr(file, 'name', 'arquivo')) for file in files]
    sizes = [str(getattr(file, 'size', '')) for file in files]
    return 'upload:' + '|'.join(names + sizes)


def _clear_estoque_outputs() -> None:
    for key in [
        'estoque_multi_outputs',
        'df_final_estoque',
        'mapping_estoque',
    ]:
        st.session_state.pop(key, None)


def _clear_estoque_outputs_if_source_changed(df_origem_site: pd.DataFrame | None, upload) -> None:
    signature = _current_source_signature(df_origem_site, upload)
    previous = st.session_state.get(ESTOQUE_SOURCE_SIGNATURE_KEY)
    if previous == signature:
        return
    _clear_estoque_outputs()
    st.session_state[ESTOQUE_SOURCE_SIGNATURE_KEY] = signature


def _clear_estoque_outputs_if_deposito_changed(deposito: str) -> None:
    signature = str(deposito or '').strip()
    previous = st.session_state.get(ESTOQUE_DEPOSITO_SIGNATURE_KEY)
    if previous is None:
        st.session_state[ESTOQUE_DEPOSITO_SIGNATURE_KEY] = signature
        return
    if previous == signature:
        return
    _clear_estoque_outputs()
    st.session_state[ESTOQUE_DEPOSITO_SIGNATURE_KEY] = signature


def _store_estoque_context(upload, df_origem_site: pd.DataFrame | None, df_modelo: pd.DataFrame | None) -> None:
    st.session_state[ESTOQUE_UPLOAD_KEY] = upload
    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        st.session_state[ESTOQUE_ORIGEM_SITE_KEY] = df_origem_site
    else:
        st.session_state.pop(ESTOQUE_ORIGEM_SITE_KEY, None)
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        st.session_state[ESTOQUE_MODELO_KEY] = df_modelo
    else:
        st.session_state.pop(ESTOQUE_MODELO_KEY, None)


def estoque_context_ready() -> bool:
    upload = st.session_state.get(ESTOQUE_UPLOAD_KEY)
    df_site = st.session_state.get(ESTOQUE_ORIGEM_SITE_KEY)
    df_modelo = st.session_state.get(ESTOQUE_MODELO_KEY)
    has_site = isinstance(df_site, pd.DataFrame) and not df_site.empty
    has_upload = bool(upload is not None and source_files_from_upload(upload))
    return (has_site or has_upload) and _valid_model(df_modelo) and _valid_deposito()


def estoque_output_ready() -> bool:
    outputs = st.session_state.get('estoque_multi_outputs')
    if isinstance(outputs, list) and outputs:
        return True
    df_final = st.session_state.get('df_final_estoque')
    return isinstance(df_final, pd.DataFrame) and not df_final.empty


def _render_deposito_input() -> str:
    current = st.session_state.get(ESTOQUE_DEPOSITO_KEY, 'Não definido')
    deposito = st.text_input(
        'Nome do depósito que será gravado no CSV',
        value=current,
        key=ESTOQUE_DEPOSITO_KEY,
        help='Este valor será aplicado em toda coluna de depósito do modelo de estoque do Bling.',
    )
    deposito = str(deposito or '').strip()
    _clear_estoque_outputs_if_deposito_changed(deposito)
    if deposito:
        st.success(f'Depósito definido para o CSV: {deposito}')
    else:
        st.error('Informe o nome do depósito antes de continuar.')
    return deposito


def render_estoque_entrada_step() -> None:
    st.markdown('### Entrada do estoque')
    st.caption('Nesta tela entra somente a origem de estoque e o nome do depósito. Preview e download ficam separados nas próximas etapas.')

    deposito = _render_deposito_input()

    model_loaded = home_estoque_model_loaded()
    if model_loaded:
        st.success('Modelo de estoque carregado. Agora informe a origem escolhida.')

    site_origin = _is_site_origin()
    df_origem_site = get_estoque_site_source() if site_origin else None
    if site_origin:
        upload = _empty_upload_result()
    else:
        upload = render_estoque_upload(model_loaded)
    _clear_estoque_outputs_if_source_changed(df_origem_site, upload)

    df_modelo = select_estoque_model(upload)
    render_estoque_model_contract(df_modelo)
    _store_estoque_context(upload, df_origem_site, df_modelo)

    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty and site_origin:
        st.success('Origem de estoque por site pronta. Continue para gerar o preview.')
    elif site_origin:
        st.info('Faça a busca por site acima. Quando a origem for criada, o botão Continuar será liberado.')
    else:
        source_files = source_files_from_upload(upload)
        if source_files:
            st.success(f'{len(source_files)} arquivo(s) de origem de estoque detectado(s).')
        else:
            st.info('Envie a origem do fornecedor para gerar o CSV final de estoque.')

    if not _valid_model(df_modelo):
        st.error('Envie o modelo de estoque do Bling antes de continuar.')
    elif not str(deposito or '').strip():
        st.error('Informe o nome do depósito antes de continuar.')


def render_estoque_gerar_step() -> None:
    st.markdown('### Gerar estoque')
    st.caption('Nesta etapa o sistema monta o CSV de estoque. O preview e o download ficam nas próximas telas.')

    upload = st.session_state.get(ESTOQUE_UPLOAD_KEY)
    df_origem_site = st.session_state.get(ESTOQUE_ORIGEM_SITE_KEY)
    df_modelo = st.session_state.get(ESTOQUE_MODELO_KEY)
    deposito = _deposito_value() or 'Não definido'

    st.info(f'Depósito que será aplicado no CSV: {deposito}')

    if not _valid_model(df_modelo):
        st.error('Modelo de estoque ausente. Volte para a entrada.')
        return
    if not _valid_deposito():
        st.error('Nome do depósito ausente. Volte para a entrada.')
        return

    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty:
        st.info('Origem de estoque veio da busca por site.')
        if st.button('Gerar preview de estoque', use_container_width=True, key='wizard_gerar_estoque_site'):
            build_stock_outputs_from_dataframe(df_origem_site, df_modelo, deposito, name='Origem criada pelo site')
    elif upload is not None and source_files_from_upload(upload):
        st.info('Origem de estoque veio de arquivo enviado.')
        if st.button('Gerar preview de estoque', use_container_width=True, key='wizard_gerar_estoque_upload'):
            build_stock_outputs(upload, df_modelo, deposito)
    else:
        st.warning('Nenhuma origem de estoque carregada. Volte para a entrada.')
        return

    if estoque_output_ready():
        st.success('Estoque gerado. Continue para conferir o preview final.')


def render_estoque_preview_step() -> None:
    st.markdown('### Preview final do estoque')
    st.caption('Confira os dados antes de baixar. O download fica na próxima etapa.')

    if not estoque_output_ready():
        st.warning('O preview de estoque ainda não foi gerado. Volte para Gerar estoque.')
        return
    render_stock_preview()


def render_estoque_download_step() -> None:
    st.markdown('### Download do estoque')
    st.caption('Última etapa: baixe somente o CSV final de atualização de estoque.')

    if not estoque_output_ready():
        st.warning('Ainda não há CSV de estoque. Volte para o preview.')
        return
    render_stock_downloads()

    st.markdown('#### Próximo passo no Bling')
    st.caption('Depois de baixar o CSV, abra direto o importador de saldos de estoque do Bling e envie o arquivo gerado.')
    st.link_button(
        '🔗 Abrir importador de estoque no Bling',
        BLING_IMPORTADOR_ESTOQUE_URL,
        use_container_width=True,
    )
