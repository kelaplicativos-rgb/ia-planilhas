from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.final_csv_exporter import final_csv_bytes
from bling_app_zero.flows.site_as_source import set_site_source_as_planilha
from bling_app_zero.flows.site_operation_router import config_for_site_operation, normalize_site_operation
from bling_app_zero.ui.home_models import save_home_models
from bling_app_zero.ui.site_progress import render_site_progress_history


def source_csv_bytes(df: pd.DataFrame) -> bytes:
    return final_csv_bytes(
        df,
        operation='origem_site',
        run_download_features=False,
    )


def _label(operation: str) -> str:
    return 'estoque' if normalize_site_operation(operation) == 'estoque' else 'cadastro'


def _mark_site_as_inline_source(normalized: str) -> None:
    """A busca por site vira origem interna para o fluxo atual."""
    st.session_state['tipo_operacao'] = normalized
    st.session_state['operacao_final'] = normalized
    st.session_state['tipo_operacao_final'] = normalized
    st.session_state['origem_final'] = 'site'
    st.session_state['origem_dados'] = 'site'
    st.session_state['origem_tipo'] = 'site'
    st.session_state['origem_planilha_via_site'] = True
    st.session_state['site_gerou_origem_planilha'] = True
    st.session_state['home_slim_flow_origin'] = 'site'
    st.session_state['home_slim_flow_operation'] = normalized
    st.session_state.pop('home_slim_active_panel', None)


def go_to_main_flow(operation: str) -> None:
    normalized = normalize_site_operation(operation)
    try:
        st.query_params['flow'] = 'site'
        st.query_params['operacao'] = normalized
        st.query_params['origem'] = 'site'
    except Exception:
        pass
    _mark_site_as_inline_source(normalized)


def save_site_source(
    df_site: pd.DataFrame,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
    operation: str = 'cadastro',
) -> None:
    normalized = normalize_site_operation(operation)
    save_home_models(df_modelo_cadastro, df_modelo_estoque)
    set_site_source_as_planilha(
        df=df_site,
        operation=normalized,
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        cadastro_model_df=df_modelo_cadastro,
        estoque_model_df=df_modelo_estoque,
        operation_model_df=df_modelo,
    )
    st.session_state['operation_site'] = normalized
    st.session_state['tipo_operacao_site'] = normalized
    _mark_site_as_inline_source(normalized)


def render_site_source_summary(
    df_site: pd.DataFrame,
    operation: str = 'cadastro',
    *,
    show_history: bool = False,
    show_sample: bool = True,
    sample_in_expander: bool = True,
) -> None:
    """Resumo leve para o Wizard: sem mapeamento, preview final ou download final.

    sample_in_expander=False evita erro do Streamlit quando este resumo é chamado
    dentro de outro expander.
    """
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return
    label = _label(operation)
    st.success(f'Origem de {label} criada com {len(df_site)} produto(s) e {len(df_site.columns)} coluna(s).')
    st.caption('Continue para a próxima etapa. O mapeamento, preview e download final ficam separados no Wizard.')

    if show_sample:
        sample = df_site.head(20).fillna('').astype(str)
        if sample_in_expander:
            with st.expander('Conferir uma amostra da origem por site', expanded=False):
                st.dataframe(sample, use_container_width=True)
        else:
            st.caption('Amostra da origem por site')
            st.dataframe(sample, use_container_width=True)

    if show_history:
        render_site_progress_history()


def render_generated_site_actions(
    df_site: pd.DataFrame,
    raw_urls: str,
    requested_columns: list[str] | None,
    df_modelo_cadastro: pd.DataFrame | None,
    df_modelo_estoque: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
    operation: str = 'cadastro',
) -> None:
    """Compatibilidade com telas antigas: salva origem e mostra download bruto opcional."""
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return

    normalized = normalize_site_operation(operation)
    label = _label(normalized)
    config = config_for_site_operation(normalized)
    save_site_source(df_site, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, normalized)

    st.success(f'Origem de {label} criada com sucesso. Siga para a próxima etapa.')
    render_site_progress_history()

    st.download_button(
        f'Baixar origem bruta de {label}',
        data=source_csv_bytes(df_site),
        file_name=config.output_filename,
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'download_origem_site_{normalized}_{len(df_site)}_{len(df_site.columns)}',
        help='Opcional: baixa apenas a origem bruta capturada no site, não é o CSV final do Bling.',
    )
