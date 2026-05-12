from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
from bling_app_zero.ui.cadastro_pricing import render_cadastro_pricing
from bling_app_zero.ui.cadastro_sources import (
    render_cadastro_source_upload,
    select_cadastro_model,
    select_estoque_model_for_cadastro,
)
from bling_app_zero.ui.cadastro_wizard_state import (
    BLING_IMPORTADOR_PRODUTOS_URL,
    CADASTRO_MODELO_KEY,
    CADASTRO_ORIGEM_KEY,
    CADASTRO_ORIGEM_PRICED_KEY,
    cadastro_context_ready,
    cadastro_mapping_ready,
    clear_cadastro_outputs_if_source_changed,
    enforce_cadastro_model_columns,
    is_site_origin,
    render_row_count_blocker,
    store_cadastro_context,
    store_expected_source_rows,
    valid_df,
    valid_model,
)
from bling_app_zero.ui.home_models import get_home_cadastro_model, get_home_estoque_model
from bling_app_zero.ui.home_shared import download_final, preview_df, show_mapping
from bling_app_zero.ui.preview_ai_actions import render_preview_ai_actions
from bling_app_zero.ui.shared_mapping import render_shared_cadastro_mapping
from bling_app_zero.ui.smart_upload import SmartUploadResult


def _empty_upload_result() -> SmartUploadResult:
    return SmartUploadResult(
        source_file=None,
        source_df=None,
        model_file=None,
        model_df=None,
        cadastro_model_file=None,
        cadastro_model_df=get_home_cadastro_model(),
        estoque_model_file=None,
        estoque_model_df=get_home_estoque_model(),
        attachments=[],
        ignored_files=[],
    )


def _source_dataframe(df_origem_site: pd.DataFrame | None, upload) -> pd.DataFrame | None:
    if isinstance(df_origem_site, pd.DataFrame):
        return df_origem_site
    source_df = getattr(upload, 'source_df', None)
    return source_df if isinstance(source_df, pd.DataFrame) else None


def render_cadastro_entrada_step() -> None:
    st.markdown('### Entrada do cadastro')
    st.caption('Carregue somente a origem do fornecedor nesta etapa. O mapeamento, preview e download ficam nas próximas telas.')

    site_origin = is_site_origin()
    df_origem_site = get_site_source_for_operation('cadastro') if site_origin else None
    upload = _empty_upload_result() if site_origin else render_cadastro_source_upload(None)
    df_origem = _source_dataframe(df_origem_site, upload)
    clear_cadastro_outputs_if_source_changed(df_origem)

    df_modelo = select_cadastro_model(upload)
    df_modelo_estoque = select_estoque_model_for_cadastro(upload)
    store_cadastro_context(df_origem, df_modelo, df_modelo_estoque)

    if valid_df(df_origem) and site_origin:
        st.success(f'Origem de cadastro por site pronta com {len(df_origem)} produto(s). Continue para o mapeamento.')
    elif valid_df(df_origem):
        st.success(f'Origem de cadastro carregada com {len(df_origem)} produto(s) e {len(df_origem.columns)} coluna(s).')
        with st.expander('Conferir origem carregada', expanded=False):
            preview_df('Origem do cadastro', df_origem)
    elif site_origin:
        st.info('Faça a busca por site acima. Quando a origem for criada, o botão Continuar será liberado.')
    elif getattr(upload, 'attachments', None):
        st.warning('Arquivo recebido, mas ainda não encontrei uma tabela válida.')
    else:
        st.info('Envie a origem do fornecedor antes de continuar.')

    if valid_model(df_modelo):
        st.caption(f'Modelo de cadastro detectado com {len(df_modelo.columns)} coluna(s).')
    else:
        st.error('Modelo de cadastro do Bling ausente. Volte na etapa Modelo e envie o modelo correto antes de continuar.')

    if valid_model(df_modelo_estoque):
        st.caption(f'Modelo de estoque também detectado com {len(df_modelo_estoque.columns)} coluna(s).')


def render_cadastro_mapeamento_step() -> None:
    st.markdown('### Mapeamento do cadastro')
    st.caption('Conferência das colunas. Preview final e download ficam separados para deixar esta tela mais leve.')

    df_origem = st.session_state.get(CADASTRO_ORIGEM_KEY)
    df_modelo = st.session_state.get(CADASTRO_MODELO_KEY)

    if not valid_df(df_origem):
        st.warning('Nenhuma origem de cadastro carregada. Volte para a etapa Entrada.')
        return
    if not valid_model(df_modelo):
        st.warning('Modelo de cadastro ausente. Volte para a etapa Modelo.')
        return

    store_expected_source_rows(df_origem)
    st.caption(f'Origem em uso no mapeamento: {len(df_origem)} produto(s).')

    df_para_mapear = render_cadastro_pricing(df_origem)
    df_para_mapear = st.session_state.get('df_origem_cadastro_precificada', df_para_mapear)
    if isinstance(df_para_mapear, pd.DataFrame):
        st.session_state[CADASTRO_ORIGEM_PRICED_KEY] = df_para_mapear
    if bool(st.session_state.get('cadastro_preco_calculado_ativo', False)):
        st.success('Precificação aplicada. O campo Preço de venda será usado como base para os campos de preço do Bling.')
    render_shared_cadastro_mapping(df_para_mapear, df_modelo)

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if isinstance(df_final, pd.DataFrame) and len(df_final) != len(df_origem):
        render_row_count_blocker(df_final)


def render_cadastro_preview_step() -> None:
    st.markdown('### Preview final do cadastro')
    st.caption('Confira o CSV final antes de baixar. Esta tela não reabre o mapeamento para evitar carga desnecessária.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    mapping = st.session_state.get('mapping_cadastro', {})

    if not valid_df(df_final):
        st.warning('O preview ainda não foi gerado. Volte para o mapeamento e confirme os campos.')
        return

    if render_row_count_blocker(df_final):
        return

    show_mapping(mapping, operation='cadastro')
    preview_df('🧾 CADASTRO · Preview final', df_final)
    render_preview_ai_actions(df_final, 'cadastro')


def render_cadastro_download_step() -> None:
    st.markdown('### Download do cadastro')
    st.caption('Última etapa: baixe somente o CSV final de cadastro pronto para o Bling.')

    df_final = enforce_cadastro_model_columns(st.session_state.get('df_final_cadastro'))
    if not valid_df(df_final):
        st.warning('Ainda não há CSV final de cadastro. Volte para o preview.')
        return

    if render_row_count_blocker(df_final):
        return

    download_final(df_final, 'cadastro', 'cadastro_wizard')

    st.markdown('#### Próximo passo no Bling')
    st.caption('Depois de baixar o CSV, abra direto o importador de produtos do Bling e envie o arquivo gerado.')
    st.link_button(
        '🔗 Abrir importador de produtos no Bling',
        BLING_IMPORTADOR_PRODUTOS_URL,
        use_container_width=True,
    )


__all__ = [
    'cadastro_context_ready',
    'cadastro_mapping_ready',
    'render_cadastro_download_step',
    'render_cadastro_entrada_step',
    'render_cadastro_mapeamento_step',
    'render_cadastro_preview_step',
]
