from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.estoque_mapping import render_manual_estoque_mapping
from bling_app_zero.ui.estoque_models import home_estoque_model_loaded, render_estoque_model_contract, select_estoque_model
from bling_app_zero.ui.estoque_outputs import render_stock_downloads, render_stock_preview
from bling_app_zero.ui.estoque_sources import (
    file_name,
    get_estoque_site_source,
    render_estoque_upload,
    safe_read_source,
    source_files_from_upload,
)
from bling_app_zero.ui.home_models import get_home_estoque_model
from bling_app_zero.ui.home_shared import df_signature
from bling_app_zero.ui.smart_upload import SmartUploadResult

ESTOQUE_SOURCE_SIGNATURE_KEY = 'estoque_source_signature_atual'
ESTOQUE_UPLOAD_KEY = 'estoque_wizard_upload'
ESTOQUE_ORIGEM_SITE_KEY = 'estoque_wizard_df_origem_site'
ESTOQUE_MODELO_KEY = 'estoque_wizard_df_modelo'
ESTOQUE_DEPOSITO_KEY = 'estoque_nome_deposito'
ESTOQUE_DEPOSITO_SIGNATURE_KEY = 'estoque_deposito_signature_atual'
ESTOQUE_DEPOSITO_ALIAS_KEYS = [
    ESTOQUE_DEPOSITO_KEY,
    'deposito_estoque',
    'nome_deposito_estoque',
    'estoque_deposito',
    'nome_deposito',
]
BLING_IMPORTADOR_ESTOQUE_URL = 'https://www.bling.com.br/importador.saldos.estoque.php'


def _valid_model(df_modelo: pd.DataFrame | None) -> bool:
    return isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns) > 0


def _normalize_deposito(value: object) -> str:
    text = str(value or '').strip()
    if text.lower() in {'não definido', 'nao definido', 'undefined', 'none', 'null'}:
        return ''
    return text


def _store_deposito_value(deposito: str, *, write_primary: bool = True) -> None:
    clean = _normalize_deposito(deposito)
    if write_primary:
        st.session_state[ESTOQUE_DEPOSITO_KEY] = clean
    for key in ESTOQUE_DEPOSITO_ALIAS_KEYS:
        if key != ESTOQUE_DEPOSITO_KEY and (key in st.session_state or clean):
            st.session_state[key] = clean


def _deposito_value() -> str:
    for key in ESTOQUE_DEPOSITO_ALIAS_KEYS:
        value = _normalize_deposito(st.session_state.get(key))
        if value:
            if key != ESTOQUE_DEPOSITO_KEY and ESTOQUE_DEPOSITO_KEY not in st.session_state:
                _store_deposito_value(value, write_primary=True)
            return value
    return ''


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
        'df_final_estoque_from_cadastro',
        'mapping_estoque_from_cadastro',
        'mapping_confidence_estoque_from_cadastro',
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
    signature = _normalize_deposito(deposito)
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


def _has_stock_source(upload=None, df_site=None) -> bool:
    current_upload = st.session_state.get(ESTOQUE_UPLOAD_KEY) if upload is None else upload
    current_site = st.session_state.get(ESTOQUE_ORIGEM_SITE_KEY) if df_site is None else df_site
    has_site = isinstance(current_site, pd.DataFrame) and not current_site.empty
    has_upload = bool(current_upload is not None and source_files_from_upload(current_upload))
    return has_site or has_upload


def estoque_context_ready() -> bool:
    df_modelo = st.session_state.get(ESTOQUE_MODELO_KEY)
    return _has_stock_source() and _valid_model(df_modelo) and _valid_deposito()


def _generated_output_ready() -> bool:
    outputs = st.session_state.get('estoque_multi_outputs')
    if isinstance(outputs, list) and outputs:
        return True
    df_final = st.session_state.get('df_final_estoque')
    return isinstance(df_final, pd.DataFrame) and not df_final.empty


def estoque_output_ready() -> bool:
    return _generated_output_ready()


def _current_stock_source() -> tuple[pd.DataFrame | None, str]:
    df_site = st.session_state.get(ESTOQUE_ORIGEM_SITE_KEY)
    if isinstance(df_site, pd.DataFrame) and not df_site.empty:
        return df_site, 'Origem criada pelo site'

    upload = st.session_state.get(ESTOQUE_UPLOAD_KEY)
    files = source_files_from_upload(upload)
    if not files:
        return None, ''
    if len(files) > 1:
        st.warning('Mapeamento manual de estoque usa uma origem por vez. Para múltiplos arquivos, gere um CSV por arquivo.')
    first_file = files[0]
    df_file = safe_read_source(first_file)
    if isinstance(df_file, pd.DataFrame) and not df_file.empty:
        return df_file, file_name(first_file)
    return None, ''


def _sync_manual_stock_output(name: str) -> bool:
    df_final = st.session_state.get('df_final_estoque_from_cadastro')
    mapping = st.session_state.get('mapping_estoque_from_cadastro', {})
    if not isinstance(df_final, pd.DataFrame) or df_final.empty:
        return False
    result = {'index': 1, 'name': name or 'Origem de estoque', 'df_final': df_final, 'mapping': mapping if isinstance(mapping, dict) else {}}
    st.session_state['estoque_multi_outputs'] = [result]
    st.session_state['df_final_estoque'] = df_final
    st.session_state['mapping_estoque'] = result['mapping']
    return True


def _build_stock_outputs_if_possible() -> bool:
    if _generated_output_ready():
        return True
    return _sync_manual_stock_output('Origem de estoque')


def _render_deposito_input() -> str:
    current = _deposito_value()
    if ESTOQUE_DEPOSITO_KEY not in st.session_state:
        st.session_state[ESTOQUE_DEPOSITO_KEY] = current

    deposito = st.text_input(
        'Nome do depósito que será gravado no CSV',
        value=current,
        key=ESTOQUE_DEPOSITO_KEY,
        placeholder='Ex: Principal, Loja 1, Galpão Central',
        help='Este valor será aplicado em toda coluna de depósito do modelo de estoque do Bling.',
    )
    deposito = _normalize_deposito(deposito)
    _store_deposito_value(deposito, write_primary=False)
    _clear_estoque_outputs_if_deposito_changed(deposito)
    if deposito:
        st.success(f'Depósito definido para o CSV: {deposito}')
    else:
        st.error('Informe o nome real do depósito antes de continuar. Não use “Não definido” nesta etapa.')
    return deposito


def _render_deposito_missing_recovery() -> str:
    st.warning('O nome do depósito não chegou nesta etapa. Informe abaixo para gerar o estoque sem voltar no fluxo.')
    deposito = _render_deposito_input()
    if not deposito:
        st.error('Geração bloqueada: o CSV de estoque precisa do depósito para preencher o modelo do Bling.')
    return deposito


def render_estoque_entrada_step() -> None:
    st.markdown('### Entrada do estoque')
    st.caption('Nesta tela entra somente a origem de estoque e o nome do depósito. O mapeamento, preview e download ficam nas próximas etapas.')

    deposito = _render_deposito_input()

    model_loaded = home_estoque_model_loaded()
    if model_loaded:
        st.success('Modelo de estoque carregado. Agora informe a origem escolhida.')

    site_origin = _is_site_origin()
    df_origem_site = get_estoque_site_source() if site_origin else None
    upload = _empty_upload_result() if site_origin else render_estoque_upload(model_loaded)
    _clear_estoque_outputs_if_source_changed(df_origem_site, upload)

    df_modelo = select_estoque_model(upload)
    render_estoque_model_contract(df_modelo)
    _store_estoque_context(upload, df_origem_site, df_modelo)

    if isinstance(df_origem_site, pd.DataFrame) and not df_origem_site.empty and site_origin:
        st.success('Origem de estoque por site pronta. Continue para conferir o mapeamento.')
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
    elif not deposito:
        st.error('Informe o nome do depósito antes de continuar.')


def render_estoque_gerar_step() -> None:
    st.markdown('### Mapeamento do estoque')
    st.caption('Mapeamento manual exclusivo de estoque. Nada deve ser criado sem você ver o campo correspondente.')

    df_modelo = st.session_state.get(ESTOQUE_MODELO_KEY)
    deposito = _deposito_value()
    df_origem, source_name = _current_stock_source()

    if deposito:
        st.success(f'Depósito que será aplicado no CSV: {deposito}')
    else:
        deposito = _render_deposito_missing_recovery()
        if not deposito:
            return

    if not _valid_model(df_modelo):
        st.error('Modelo de estoque ausente. Volte para a entrada.')
        return
    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        st.warning('Nenhuma origem de estoque carregada. Volte para a entrada.')
        return

    st.info(f'Origem em uso no mapeamento: {source_name or "Origem de estoque"}')
    render_manual_estoque_mapping(df_origem, df_modelo, deposito)

    if _sync_manual_stock_output(source_name):
        st.success('Mapeamento de estoque gerado. Continue para conferir o preview final.')


def render_estoque_preview_step() -> None:
    st.markdown('### Preview final do estoque')
    st.caption('Confira os dados antes de baixar. O download fica na próxima etapa.')

    if not _build_stock_outputs_if_possible():
        st.warning('O preview de estoque ainda não foi gerado. Volte para o mapeamento do estoque.')
        return
    render_stock_preview()


def render_estoque_download_step() -> None:
    st.markdown('### Download do estoque')
    st.caption('Última etapa: baixe somente o CSV final de atualização de estoque.')

    if not _build_stock_outputs_if_possible():
        st.warning('Ainda não há CSV de estoque. Volte para o mapeamento do estoque.')
        return
    render_stock_downloads()

    st.markdown('#### Próximo passo no Bling')
    st.caption('Depois de baixar o CSV, abra direto o importador de saldos de estoque do Bling e envie o arquivo gerado.')
    st.link_button(
        '🔗 Abrir importador de estoque no Bling',
        BLING_IMPORTADOR_ESTOQUE_URL,
        use_container_width=True,
    )
