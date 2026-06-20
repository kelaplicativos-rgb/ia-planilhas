from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.final_csv_exporter import final_csv_bytes
from bling_app_zero.core.site_diag_frames_min import sync_site_diag_frames
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


def _sync_site_diagnostic_safe() -> None:
    try:
        sync_site_diag_frames()
    except Exception:
        pass


def _requested_columns(requested_columns: list[str] | None) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for column in requested_columns or []:
        text = str(column or '').strip()
        if text and text not in seen:
            columns.append(text)
            seen.add(text)
    return columns


def _stock_contract_df(df_site: pd.DataFrame, requested_columns: list[str] | None) -> pd.DataFrame:
    df = df_site.copy().fillna('') if isinstance(df_site, pd.DataFrame) else pd.DataFrame()
    columns = _requested_columns(requested_columns)
    if not columns:
        return df
    return df.reindex(columns=columns, fill_value='')


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
    _sync_site_diagnostic_safe()


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
    df_to_save = _stock_contract_df(df_site, requested_columns) if normalized == 'estoque' else df_site
    if normalized == 'estoque':
        st.session_state['site_stock_requested_columns_enforced'] = True
        st.session_state['site_stock_requested_columns_count'] = len(_requested_columns(requested_columns))
    save_home_models(df_modelo_cadastro, df_modelo_estoque)
    set_site_source_as_planilha(
        df=df_to_save,
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
    _sync_site_diagnostic_safe()


def render_site_source_summary(
    df_site: pd.DataFrame,
    operation: str = 'cadastro',
    *,
    show_history: bool = False,
    show_sample: bool = False,
    sample_in_expander: bool = True,
) -> None:
    """Resumo mínimo antes do mapeamento.

    A etapa Dados não deve virar uma tela longa depois da captura. O objetivo é
    confirmar que a origem ficou pronta e deixar o usuário seguir direto para o
    mapeamento manual.
    """
    if not isinstance(df_site, pd.DataFrame) or df_site.empty:
        return
    _sync_site_diagnostic_safe()
    st.success(f'Origem pronta: {len(df_site)} registro(s). Siga para o mapeamento abaixo.')

    if show_sample:
        sample = df_site.head(20).fillna('').astype(str)
        if sample_in_expander:
            with st.expander('Ver amostra da origem', expanded=False):
                st.dataframe(sample, use_container_width=True)
        else:
            st.caption('Amostra da origem')
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
    config = config_for_site_operation(normalized)
    df_to_save = _stock_contract_df(df_site, requested_columns) if normalized == 'estoque' else df_site
    save_site_source(df_to_save, raw_urls, requested_columns, df_modelo_cadastro, df_modelo_estoque, df_modelo, normalized)
    _sync_site_diagnostic_safe()

    st.success('Origem por site criada. Siga para o mapeamento abaixo.')
    render_site_progress_history()

    st.download_button(
        'Baixar origem bruta',
        data=source_csv_bytes(df_to_save),
        file_name=config.output_filename,
        mime='text/csv; charset=utf-8',
        use_container_width=True,
        key=f'download_origem_site_{normalized}_{len(df_to_save)}_{len(df_to_save.columns)}',
        help='Opcional: baixa apenas a origem bruta capturada no site; não é a planilha final.',
    )
