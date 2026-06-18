from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_intelligence import DEFAULT_CATEGORY_CATALOG, apply_category_suggestions, classify_dataframe, detect_category_column
from bling_app_zero.core.global_dataset_guard import (
    GLOBAL_DECISION_DATASET_SIGNATURE_KEY,
    GLOBAL_LIVE_DATASET_SIGNATURE_KEY,
    category_values_signature as global_category_values_signature,
    dataframe_identity_signature,
    dataframe_table_signature,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/category_conference_step_v2.py'
CATEGORY_DONE_KEY = 'category_conference_confirmed_v1'
CATEGORY_SKIP_KEY = 'category_conference_skipped_v1'
CATEGORY_STATS_KEY = 'category_conference_stats_v1'
CATEGORY_ANALYZED_KEY = 'category_conference_analyzed_df_v1'
CATEGORY_CATALOG_KEY = 'category_conference_catalog_text_v1'
CATEGORY_SOURCE_SIGNATURE_KEY = 'category_conference_source_signature_v1'
CATEGORY_VALUES_SIGNATURE_KEY = 'category_conference_values_signature_v1'
CATEGORY_DATASET_SIGNATURE_KEY = 'category_conference_dataset_signature_v1'

DATAFRAME_KEYS = (
    'df_final_bling_api', 'df_final_universal', 'df_final_cadastro', 'df_final_cadastro_preview_rules_applied',
    'df_final_download_operation', 'df_final_preview_operation', 'final_download_df_snapshot',
    'cadastro_wizard_df_origem', 'cadastro_wizard_df_para_mapear', 'df_origem_cadastro_precificada',
    'df_origem_site_como_planilha', 'df_origem_site_como_planilha_cadastro', 'df_origem_site_como_planilha_universal',
    'df_produtos_origem', 'df_origem', 'df_origem_planilha', 'df_origem_cadastro', 'df_origem_universal',
    'df_site_bruto', 'df_site_bruto_cadastro', 'df_site_bruto_universal',
)

PRIMARY_KEYS = (
    'cadastro_wizard_df_origem', 'df_origem_cadastro_precificada', 'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_cadastro', 'df_origem_site_como_planilha_universal', 'df_produtos_origem',
    'cadastro_wizard_df_para_mapear', 'df_origem', 'df_origem_planilha', 'df_origem_cadastro', 'df_origem_universal',
    'df_final_bling_api', 'df_final_universal', 'df_final_cadastro',
)


def _valid_df(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and not value.empty and len(value.columns) > 0


def _source_df() -> tuple[pd.DataFrame | None, str]:
    for key in PRIMARY_KEYS:
        value = st.session_state.get(key)
        if _valid_df(value):
            return value.copy().fillna(''), key
    return None, ''


def _source_signature(df: pd.DataFrame, source_key: str) -> str:
    return f'{source_key}:{dataframe_table_signature(df, context="category_conference_source")}'


def _dataset_identity(df: pd.DataFrame) -> str:
    return dataframe_identity_signature(df, context='category_conference').signature


def category_values_signature(df: pd.DataFrame) -> str:
    category_col = detect_category_column(df) if _valid_df(df) else None
    return global_category_values_signature(df, category_col, context='category_conference')


def _reset_if_source_changed(df: pd.DataFrame, source_key: str) -> None:
    signature = _source_signature(df, source_key)
    previous = str(st.session_state.get(CATEGORY_SOURCE_SIGNATURE_KEY) or '')
    if previous and previous != signature:
        for key in (
            CATEGORY_DONE_KEY, CATEGORY_SKIP_KEY, CATEGORY_STATS_KEY, CATEGORY_ANALYZED_KEY,
            CATEGORY_VALUES_SIGNATURE_KEY, CATEGORY_DATASET_SIGNATURE_KEY, GLOBAL_DECISION_DATASET_SIGNATURE_KEY,
        ):
            st.session_state.pop(key, None)
        add_audit_event(
            'category_conference_live_source_changed',
            area='CATEGORIAS',
            step='conferencia_categorias',
            status='OK',
            details={'previous_signature': previous, 'current_signature': signature, 'cache_invalidated': True, 'full_table_signature': True, 'responsible_file': RESPONSIBLE_FILE},
        )
    st.session_state[CATEGORY_SOURCE_SIGNATURE_KEY] = signature
    st.session_state[GLOBAL_LIVE_DATASET_SIGNATURE_KEY] = _dataset_identity(df)


def _csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, sep=';', encoding='utf-8-sig')
    return buffer.getvalue().encode('utf-8-sig')


def _catalog() -> tuple[str, ...]:
    text = str(st.session_state.get(CATEGORY_CATALOG_KEY) or '').strip()
    if not text:
        return DEFAULT_CATEGORY_CATALOG
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _apply_category_values(target: pd.DataFrame, corrected: pd.DataFrame) -> pd.DataFrame:
    result = target.copy().fillna('')
    source_col = detect_category_column(corrected) or 'Categoria'
    target_col = detect_category_column(result) or 'Categoria'
    if target_col not in result.columns:
        result[target_col] = ''
    if source_col not in corrected.columns:
        return result
    limit = min(len(result), len(corrected))
    result.loc[result.index[:limit], target_col] = corrected[source_col].astype(str).iloc[:limit].to_list()
    return result


def _store_corrected_everywhere(corrected: pd.DataFrame, source_key: str, *, applied_count: int, stats: dict[str, int]) -> None:
    if not _valid_df(corrected):
        return
    for key in DATAFRAME_KEYS:
        value = st.session_state.get(key)
        if _valid_df(value) and len(value) == len(corrected):
            st.session_state[key] = _apply_category_values(value, corrected)
    if source_key:
        st.session_state[source_key] = corrected.copy().fillna('')
    dataset_sig = _dataset_identity(corrected)
    st.session_state[CATEGORY_DONE_KEY] = True
    st.session_state[CATEGORY_SKIP_KEY] = False
    st.session_state[CATEGORY_SOURCE_SIGNATURE_KEY] = _source_signature(corrected, source_key)
    st.session_state[CATEGORY_VALUES_SIGNATURE_KEY] = category_values_signature(corrected)
    st.session_state[CATEGORY_DATASET_SIGNATURE_KEY] = dataset_sig
    st.session_state[GLOBAL_DECISION_DATASET_SIGNATURE_KEY] = dataset_sig
    st.session_state[GLOBAL_LIVE_DATASET_SIGNATURE_KEY] = dataset_sig
    st.session_state[CATEGORY_STATS_KEY] = dict(stats or {})
    add_audit_event(
        'category_conference_applied',
        area='CATEGORIAS',
        step='conferencia_categorias',
        status='OK',
        details={
            'rows': int(len(corrected)), 'columns': int(len(corrected.columns)), 'source_key': source_key,
            'applied_count': int(applied_count), 'stats': dict(stats or {}),
            'category_column': detect_category_column(corrected), 'category_values_signature': st.session_state.get(CATEGORY_VALUES_SIGNATURE_KEY),
            'dataset_identity_signature': dataset_sig, 'full_table_signature': st.session_state.get(CATEGORY_SOURCE_SIGNATURE_KEY),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def category_conference_ready() -> bool:
    return bool(st.session_state.get(CATEGORY_DONE_KEY) or st.session_state.get(CATEGORY_SKIP_KEY))


def category_conference_was_skipped() -> bool:
    return bool(st.session_state.get(CATEGORY_SKIP_KEY))


def render_category_conference_step() -> None:
    df, source_key = _source_df()
    if not _valid_df(df):
        st.warning('Nenhuma base de produtos carregada para conferir categorias.')
        return
    _reset_if_source_changed(df, source_key)

    st.markdown('### Conferência inteligente de categorias')
    st.caption('Corrige plural, ortografia, categorias genéricas e erros de digitação antes do envio ao Bling.')
    st.warning('Proteção anti-cache: se qualquer linha da base viva mudar, a confirmação antiga é invalidada automaticamente.')

    if CATEGORY_CATALOG_KEY not in st.session_state:
        st.session_state[CATEGORY_CATALOG_KEY] = '\n'.join(DEFAULT_CATEGORY_CATALOG)
    with st.expander('Catálogo oficial de categorias', expanded=False):
        st.text_area('Uma categoria por linha', height=210, key=CATEGORY_CATALOG_KEY, help='Este catálogo define o nome final correto que será enviado/criado no Bling.')

    confidence_min = st.slider('Confiança mínima para aplicar automaticamente', 0.50, 1.00, 0.80, 0.05, key='category_conference_confidence_min_v1')
    analyzed, stats = classify_dataframe(df, category_catalog=_catalog())
    st.session_state[CATEGORY_ANALYZED_KEY] = analyzed
    st.session_state[CATEGORY_STATS_KEY] = stats

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric('Produtos', stats.get('total', 0))
    col2.metric('Sem categoria', stats.get('sem_categoria', 0))
    col3.metric('Corrigir', stats.get('corrigir', 0))
    col4.metric('Criar/vincular', stats.get('criar_vincular', 0))
    col5.metric('Revisar', stats.get('revisar', 0))

    action_df = analyzed[analyzed['acao_categoria_ia'] != 'MANTER'].copy() if 'acao_categoria_ia' in analyzed.columns else pd.DataFrame()
    if action_df.empty:
        st.success('Todas as categorias estão padronizadas.')
    else:
        display_cols = [col for col in ('Nome', 'Descrição', 'Descricao', 'Produto', 'categoria_atual_ia', 'categoria_sugerida_ia', 'acao_categoria_ia', 'confianca_categoria_ia', 'motivo_categoria_ia') if col in action_df.columns]
        st.dataframe(action_df[display_cols].head(500), use_container_width=True, hide_index=True, height=360)
        if len(action_df) > 500:
            st.caption(f'Mostrando 500 de {len(action_df)} produtos com ação de categoria.')

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button('Aplicar categorias corrigidas', type='primary', use_container_width=True, key='category_conference_apply_v1'):
            corrected, applied_count = apply_category_suggestions(analyzed.copy(), confidence_min=confidence_min, keep_helper_columns=False)
            _store_corrected_everywhere(corrected, source_key, applied_count=applied_count, stats=stats)
            st.success(f'{applied_count} categoria(s) corrigida(s)/padronizada(s).')
            st.rerun()
    with c2:
        if st.button('Pular sem alterar categorias', use_container_width=True, key='category_conference_skip_v1'):
            dataset_sig = _dataset_identity(df)
            st.session_state[CATEGORY_SKIP_KEY] = True
            st.session_state[CATEGORY_DONE_KEY] = False
            st.session_state[CATEGORY_SOURCE_SIGNATURE_KEY] = _source_signature(df, source_key)
            st.session_state[CATEGORY_VALUES_SIGNATURE_KEY] = category_values_signature(df)
            st.session_state[CATEGORY_DATASET_SIGNATURE_KEY] = dataset_sig
            st.session_state[GLOBAL_DECISION_DATASET_SIGNATURE_KEY] = dataset_sig
            st.session_state[GLOBAL_LIVE_DATASET_SIGNATURE_KEY] = dataset_sig
            add_audit_event(
                'category_conference_skipped_by_user',
                area='CATEGORIAS',
                step='conferencia_categorias',
                status='PULADO',
                details={'rows': int(len(df)), 'source_key': source_key, 'category_values_signature': st.session_state.get(CATEGORY_VALUES_SIGNATURE_KEY), 'dataset_identity_signature': dataset_sig, 'responsible_file': RESPONSIBLE_FILE},
            )
            st.warning('Etapa pulada pelo usuário. O sistema não alterará categorias nesta execução.')
            st.rerun()
    with c3:
        st.download_button('Baixar relatório da conferência', data=_csv_bytes(analyzed), file_name='conferencia_inteligente_categorias.csv', mime='text/csv', use_container_width=True, key='category_conference_download_v1')

    if category_conference_was_skipped():
        st.warning('Conferência pulada. O envio usará as categorias exatamente como estão na origem viva atual.')
    elif category_conference_ready():
        st.success('Conferência confirmada. O envio ao Bling usará o nome corrigido da categoria.')
    else:
        st.info('Aplique as categorias corrigidas ou pule explicitamente para liberar o envio.')


__all__ = [
    'CATEGORY_DATASET_SIGNATURE_KEY', 'CATEGORY_DONE_KEY', 'CATEGORY_SKIP_KEY', 'CATEGORY_VALUES_SIGNATURE_KEY',
    'category_values_signature', 'category_conference_ready', 'category_conference_was_skipped', 'render_category_conference_step',
]
