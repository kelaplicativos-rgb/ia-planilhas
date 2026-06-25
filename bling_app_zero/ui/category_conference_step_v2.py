from __future__ import annotations

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
CATEGORY_AUTO_APPLIED_SIGNATURE_KEY = 'category_conference_auto_applied_signature_v1'
CATEGORY_AUTO_BLOCKED_SIGNATURE_KEY = 'category_conference_auto_blocked_signature_v1'
CATEGORY_REBUILD_BUTTON_KEY = 'category_conference_rebuild_auto_v1'
CATEGORY_REVIEW_SEARCH_KEY = 'category_conference_review_search_v1'
CATEGORY_REVIEW_ACTION_KEY = 'category_conference_review_action_v1'
CATEGORY_REVIEW_CATEGORY_KEY = 'category_conference_review_category_v1'
CATEGORY_REVIEW_ONLY_ATTENTION_KEY = 'category_conference_review_only_attention_v1'
CATEGORY_REVIEW_EDITOR_KEY = 'category_conference_review_editor_v1'
CATEGORY_REVIEW_APPLY_KEY = 'category_conference_review_apply_v1'

# Não existe controle manual de confiança. Ao ligar a categorização, o sistema
# aplica automaticamente e libera um preview filtrável para conferência/correção.
CATEGORY_AUTO_CONFIDENCE_MIN = 0.80
BLOCKED_FINAL_CATEGORY_VALUES = {'', 'nan', 'none', 'null', '<na>', 'na', 'n/a', 'sem categoria', 'revisar manualmente'}

DATAFRAME_KEYS = (
    'df_final_bling_api', 'df_final_universal', 'df_final_cadastro', 'df_final_cadastro_preview_rules_applied',
    'df_final_download_operation', 'df_final_preview_operation', 'final_download_df_snapshot',
    'df_origem_cadastro_precificada', 'cadastro_wizard_df_origem', 'cadastro_wizard_df_para_mapear',
    'df_origem_site_como_planilha', 'df_origem_site_como_planilha_cadastro', 'df_origem_site_como_planilha_universal',
    'df_produtos_origem', 'df_origem', 'df_origem_planilha', 'df_origem_cadastro', 'df_origem_universal',
    'df_site_bruto', 'df_site_bruto_cadastro', 'df_site_bruto_universal',
)

# Depois da Precificação, o painel deve analisar a base já formulada com preços.
# A base crua continua como fallback para operações sem precificação.
PRIMARY_KEYS = (
    'df_origem_cadastro_precificada', 'cadastro_wizard_df_origem', 'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_cadastro', 'df_origem_site_como_planilha_universal', 'df_produtos_origem',
    'cadastro_wizard_df_para_mapear', 'df_origem', 'df_origem_planilha', 'df_origem_cadastro', 'df_origem_universal',
    'df_final_bling_api', 'df_final_universal', 'df_final_cadastro',
)

PRODUCT_COLUMNS = ('Nome', 'Descrição', 'Descricao', 'Produto', 'Título', 'Titulo', 'name', 'produto')
CODE_COLUMNS = ('Código', 'Codigo', 'SKU', 'GTIN', 'EAN', 'ID', 'Id')


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


def _final_category_issue_rows(df: pd.DataFrame) -> tuple[int, ...]:
    """Linhas 1-based sem categoria final válida após aplicar IA/manual."""
    if not _valid_df(df):
        return tuple()
    category_col = detect_category_column(df)
    if not category_col or category_col not in df.columns:
        return tuple(range(1, int(len(df)) + 1))
    bad_rows: list[int] = []
    for pos, value in enumerate(df[category_col].fillna('').astype(str), start=1):
        normalized = ' '.join(str(value or '').strip().lower().split())
        if normalized in BLOCKED_FINAL_CATEGORY_VALUES:
            bad_rows.append(pos)
    return tuple(bad_rows)


def _category_issue_preview(df: pd.DataFrame, rows: tuple[int, ...], *, limit: int = 80) -> pd.DataFrame:
    if not _valid_df(df) or not rows:
        return pd.DataFrame()
    indexes = [row - 1 for row in rows[:limit] if 0 <= row - 1 < len(df)]
    preview = df.iloc[indexes].copy().fillna('')
    preview.insert(0, 'linha', [row for row in rows[:len(indexes)]])
    preferred = [
        'linha', 'Código', 'SKU', 'GTIN', 'Nome', 'Descrição', 'Descricao', 'Produto', 'Categoria', 'Categoria do produto',
        'categoria_atual_ia', 'categoria_sugerida_ia', 'acao_categoria_ia', 'confianca_categoria_ia', 'motivo_categoria_ia',
    ]
    cols = [col for col in preferred if col in preview.columns]
    return preview[cols] if cols else preview


def _reset_if_source_changed(df: pd.DataFrame, source_key: str) -> None:
    signature = _source_signature(df, source_key)
    previous = str(st.session_state.get(CATEGORY_SOURCE_SIGNATURE_KEY) or '')
    if previous and previous != signature:
        _clear_category_decision_state(reason='live_source_changed', keep_source_signature=True)
        add_audit_event(
            'category_conference_live_source_changed',
            area='CATEGORIAS',
            step='conferencia_categorias',
            status='OK',
            details={'previous_signature': previous, 'current_signature': signature, 'cache_invalidated': True, 'full_table_signature': True, 'responsible_file': RESPONSIBLE_FILE},
        )
    st.session_state[CATEGORY_SOURCE_SIGNATURE_KEY] = signature
    st.session_state[GLOBAL_LIVE_DATASET_SIGNATURE_KEY] = _dataset_identity(df)


def _clear_category_decision_state(*, reason: str, keep_source_signature: bool = False) -> None:
    keys = [
        CATEGORY_DONE_KEY,
        CATEGORY_SKIP_KEY,
        CATEGORY_STATS_KEY,
        CATEGORY_ANALYZED_KEY,
        CATEGORY_VALUES_SIGNATURE_KEY,
        CATEGORY_DATASET_SIGNATURE_KEY,
        GLOBAL_DECISION_DATASET_SIGNATURE_KEY,
        CATEGORY_AUTO_APPLIED_SIGNATURE_KEY,
        CATEGORY_AUTO_BLOCKED_SIGNATURE_KEY,
    ]
    if not keep_source_signature:
        keys.append(CATEGORY_SOURCE_SIGNATURE_KEY)
    removed = []
    for key in keys:
        if key in st.session_state:
            removed.append(key)
            st.session_state.pop(key, None)
    add_audit_event(
        'category_conference_auto_rebuild_requested',
        area='CATEGORIAS',
        step='conferencia_categorias',
        status='OK',
        details={'reason': reason, 'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
    )


def _catalog() -> tuple[str, ...]:
    text = str(st.session_state.get(CATEGORY_CATALOG_KEY) or '').strip()
    if not text:
        return DEFAULT_CATEGORY_CATALOG
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _category_col_or_default(df: pd.DataFrame) -> str:
    return detect_category_column(df) or 'Categoria do produto'


def _apply_category_values(target: pd.DataFrame, corrected: pd.DataFrame) -> pd.DataFrame:
    result = target.copy().fillna('')
    source_col = detect_category_column(corrected) or 'Categoria do produto'
    target_col = detect_category_column(result) or 'Categoria do produto'
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
    blocked_rows = _final_category_issue_rows(corrected)
    if blocked_rows:
        st.session_state[CATEGORY_DONE_KEY] = False
        st.session_state[CATEGORY_SKIP_KEY] = False
        add_audit_event(
            'category_conference_store_blocked_incomplete',
            area='CATEGORIAS',
            step='conferencia_categorias',
            status='BLOQUEADO',
            details={
                'rows': int(len(corrected)),
                'blocked_rows_count': len(blocked_rows),
                'blocked_rows_sample': list(blocked_rows[:50]),
                'category_column': detect_category_column(corrected),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
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
            'category_completion_required': True, 'blocked_rows_count': 0, 'required_completion_percent': 100,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _apply_or_block(analyzed: pd.DataFrame, source_key: str, *, stats: dict[str, int]) -> tuple[bool, tuple[int, ...], int, pd.DataFrame]:
    corrected, applied_count = apply_category_suggestions(analyzed.copy(), confidence_min=CATEGORY_AUTO_CONFIDENCE_MIN, keep_helper_columns=False)
    blocked_rows = _final_category_issue_rows(corrected)
    if blocked_rows:
        st.session_state[CATEGORY_DONE_KEY] = False
        st.session_state[CATEGORY_SKIP_KEY] = False
        st.session_state[CATEGORY_AUTO_BLOCKED_SIGNATURE_KEY] = _dataset_identity(corrected)
        add_audit_event(
            'category_conference_automatic_blocked_incomplete',
            area='CATEGORIAS',
            step='conferencia_categorias',
            status='BLOQUEADO',
            details={
                'rows': int(len(corrected)),
                'applied_count': int(applied_count),
                'blocked_rows_count': len(blocked_rows),
                'blocked_rows_sample': list(blocked_rows[:50]),
                'required_completion_percent': 100,
                'category_column': detect_category_column(corrected),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return False, blocked_rows, int(applied_count), corrected
    _store_corrected_everywhere(corrected, source_key, applied_count=applied_count, stats=stats)
    st.session_state[CATEGORY_AUTO_APPLIED_SIGNATURE_KEY] = _dataset_identity(corrected)
    add_audit_event(
        'category_conference_automatic_completed',
        area='CATEGORIAS',
        step='conferencia_categorias',
        status='OK',
        details={'rows': int(len(corrected)), 'applied_count': int(applied_count), 'required_completion_percent': 100, 'responsible_file': RESPONSIBLE_FILE},
    )
    return True, tuple(), int(applied_count), corrected


def _render_blocked(blocked_rows: tuple[int, ...], analyzed: pd.DataFrame) -> None:
    st.error(f'Categorização automática bloqueada: {len(blocked_rows)} produto(s) ainda ficaram sem categoria final válida.')
    st.warning('Trava 100% ativa: nenhum produto será liberado para envio ao Bling enquanto existir categoria vazia ou “REVISAR MANUALMENTE”.')
    preview = _category_issue_preview(analyzed, blocked_rows)
    if _valid_df(preview):
        st.dataframe(preview, use_container_width=True, hide_index=True, height=360)


def _first_existing_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for column in candidates:
        if column in df.columns:
            return column
    return ''


def _row_text(row: pd.Series, columns: tuple[str, ...]) -> str:
    values: list[str] = []
    for column in columns:
        if column in row.index:
            value = str(row.get(column) or '').strip()
            if value:
                values.append(value)
    return ' · '.join(values)


def _build_review_preview(analyzed: pd.DataFrame) -> pd.DataFrame:
    if not _valid_df(analyzed):
        return pd.DataFrame()
    category_col = _category_col_or_default(analyzed)
    if category_col not in analyzed.columns:
        analyzed = analyzed.copy().fillna('')
        analyzed[category_col] = ''
    product_col = _first_existing_column(analyzed, PRODUCT_COLUMNS)
    code_col = _first_existing_column(analyzed, CODE_COLUMNS)
    rows: list[dict[str, object]] = []
    # Use posição real, não o índice interno do DataFrame. Isso evita aplicar
    # correção manual na linha errada quando a planilha chega com índice quebrado.
    for position, (_idx, row) in enumerate(analyzed.fillna('').iterrows()):
        current = str(row.get('categoria_atual_ia') or row.get(category_col) or '').strip()
        suggested = str(row.get('categoria_sugerida_ia') or row.get(category_col) or '').strip()
        action = str(row.get('acao_categoria_ia') or 'MANTER').strip() or 'MANTER'
        final_category = suggested or current
        rows.append(
            {
                '__row_index': int(position),
                'linha': int(position) + 1,
                'Produto': str(row.get(product_col) or _row_text(row, PRODUCT_COLUMNS) or '').strip(),
                'Código/SKU': str(row.get(code_col) or _row_text(row, CODE_COLUMNS) or '').strip(),
                'Categoria atual': current,
                'Categoria sugerida': suggested,
                'Categoria corrigida': final_category,
                'Ação': action,
                'Confiança': row.get('confianca_categoria_ia', ''),
                'Motivo': str(row.get('motivo_categoria_ia') or '').strip(),
            }
        )
    return pd.DataFrame(rows)


def _filter_review_preview(preview: pd.DataFrame) -> pd.DataFrame:
    if not _valid_df(preview):
        return preview
    with st.container(border=True):
        st.markdown('**Conferência rápida de produtos e categorias**')
        left, middle, right = st.columns([2, 1, 1])
        search = left.text_input('Filtrar por produto, código ou categoria', key=CATEGORY_REVIEW_SEARCH_KEY, placeholder='Ex.: power bank, cabo, fonte, adaptador...')
        action_options = ['Todas'] + sorted({str(value) for value in preview['Ação'].fillna('').astype(str) if str(value).strip()})
        action = middle.selectbox('Ação', action_options, key=CATEGORY_REVIEW_ACTION_KEY)
        categories = sorted({str(value).strip() for value in preview['Categoria corrigida'].fillna('').astype(str) if str(value).strip()})
        category = right.selectbox('Categoria', ['Todas'] + categories, key=CATEGORY_REVIEW_CATEGORY_KEY)
        only_attention = st.checkbox('Mostrar primeiro somente produtos corrigidos/revisar', value=False, key=CATEGORY_REVIEW_ONLY_ATTENTION_KEY)

    filtered = preview.copy().fillna('')
    if search.strip():
        token = search.strip().casefold()
        haystack = filtered.drop(columns=['__row_index'], errors='ignore').astype(str).agg(' '.join, axis=1).str.casefold()
        filtered = filtered[haystack.str.contains(token, regex=False, na=False)]
    if action != 'Todas':
        filtered = filtered[filtered['Ação'].astype(str) == action]
    if category != 'Todas':
        filtered = filtered[filtered['Categoria corrigida'].astype(str) == category]
    if only_attention:
        filtered = filtered[filtered['Ação'].astype(str).ne('MANTER')]
    return filtered


def _category_options(preview: pd.DataFrame) -> list[str]:
    options = list(_catalog())
    extra = []
    if _valid_df(preview):
        for column in ('Categoria atual', 'Categoria sugerida', 'Categoria corrigida'):
            if column in preview.columns:
                extra.extend([str(value).strip() for value in preview[column].fillna('').astype(str) if str(value).strip()])
    return sorted(dict.fromkeys([*options, *extra]))


def _editor_row_to_base_index(row: pd.Series, max_rows: int) -> int | None:
    """Resolve a linha da base mesmo se o data_editor não devolver coluna oculta.

    O caminho preferencial é __row_index, mas algumas versões/configurações do
    Streamlit podem não devolver colunas fora do column_order. Nesse caso usamos
    a coluna visível `linha`, que é 1-based.
    """
    candidates: list[tuple[object, bool]] = []
    if '__row_index' in row.index:
        candidates.append((row.get('__row_index'), False))
    if 'linha' in row.index:
        candidates.append((row.get('linha'), True))
    for value, one_based in candidates:
        try:
            if value is None or pd.isna(value):
                continue
        except Exception:
            pass
        try:
            number = int(float(str(value).strip()))
        except Exception:
            continue
        index = number - 1 if one_based else number
        if 0 <= index < max_rows:
            return index
    return None


def _apply_manual_review_edits(base_df: pd.DataFrame, edited: pd.DataFrame, source_key: str) -> int:
    if not _valid_df(base_df) or not _valid_df(edited):
        return 0
    corrected = base_df.copy().fillna('')
    category_col = _category_col_or_default(corrected)
    if category_col not in corrected.columns:
        corrected[category_col] = ''
    changed = 0
    skipped_without_index = 0
    for _, row in edited.iterrows():
        row_index = _editor_row_to_base_index(row, len(corrected))
        if row_index is None:
            skipped_without_index += 1
            continue
        new_value = str(row.get('Categoria corrigida') or '').strip()
        if not new_value:
            continue
        old_value = str(corrected.at[corrected.index[row_index], category_col] or '').strip()
        if new_value != old_value:
            corrected.at[corrected.index[row_index], category_col] = new_value
            changed += 1
    if changed <= 0:
        if skipped_without_index:
            add_audit_event(
                'category_conference_manual_review_no_row_index',
                area='CATEGORIAS',
                step='conferencia_categorias',
                status='AVISO',
                details={'skipped_rows': skipped_without_index, 'edited_rows': int(len(edited)), 'responsible_file': RESPONSIBLE_FILE},
            )
        return 0
    _analyzed_after, stats_after = classify_dataframe(corrected, category_catalog=_catalog())
    _store_corrected_everywhere(corrected, source_key, applied_count=changed, stats=stats_after)
    add_audit_event(
        'category_conference_manual_review_applied',
        area='CATEGORIAS',
        step='conferencia_categorias',
        status='OK',
        details={
            'manual_changes': changed,
            'rows': int(len(corrected)),
            'category_column': category_col,
            'fallback_visible_line_enabled': True,
            'skipped_rows_without_index': skipped_without_index,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return changed


def _render_category_review_grid(analyzed: pd.DataFrame, base_df: pd.DataFrame, source_key: str) -> None:
    preview = _build_review_preview(analyzed)
    if not _valid_df(preview):
        st.info('Não encontrei produtos para exibir na conferência de categorias.')
        return
    filtered = _filter_review_preview(preview)
    st.caption(f'Mostrando {len(filtered)} de {len(preview)} produto(s). Edite apenas a coluna “Categoria corrigida” e aplique antes de avançar.')
    if filtered.empty:
        st.info('Nenhum produto encontrado com estes filtros.')
        return
    options = _category_options(preview)
    column_config = {
        'Categoria corrigida': st.column_config.SelectboxColumn('Categoria corrigida', options=options, required=True),
        'linha': st.column_config.NumberColumn('Linha', disabled=True),
        'Produto': st.column_config.TextColumn('Produto', disabled=True),
        'Código/SKU': st.column_config.TextColumn('Código/SKU', disabled=True),
        'Categoria atual': st.column_config.TextColumn('Categoria atual', disabled=True),
        'Categoria sugerida': st.column_config.TextColumn('Categoria sugerida', disabled=True),
        'Ação': st.column_config.TextColumn('Ação', disabled=True),
        'Confiança': st.column_config.TextColumn('Confiança', disabled=True),
        'Motivo': st.column_config.TextColumn('Motivo', disabled=True),
    }
    edited = st.data_editor(
        filtered,
        key=CATEGORY_REVIEW_EDITOR_KEY,
        use_container_width=True,
        hide_index=True,
        height=430,
        disabled=[col for col in filtered.columns if col not in {'Categoria corrigida'}],
        column_config=column_config,
        column_order=['linha', 'Produto', 'Código/SKU', 'Categoria atual', 'Categoria sugerida', 'Categoria corrigida', 'Ação', 'Confiança', 'Motivo'],
    )
    if st.button('✅ Aplicar correções manuais de categoria', use_container_width=True, key=CATEGORY_REVIEW_APPLY_KEY):
        changed = _apply_manual_review_edits(base_df, edited, source_key)
        if changed:
            st.success(f'{changed} categoria(s) corrigida(s) manualmente e aplicadas na base final.')
            st.rerun()
        else:
            st.info('Nenhuma categoria manual diferente foi informada neste filtro.')


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
    st.caption('A categorização automática padroniza primeiro; depois você confere por filtros e corrige manualmente em uma grade rápida.')
    st.warning('Trava 100%: nenhum produto será liberado enquanto existir categoria final vazia ou “REVISAR MANUALMENTE”.')

    if CATEGORY_CATALOG_KEY not in st.session_state:
        st.session_state[CATEGORY_CATALOG_KEY] = '\n'.join(DEFAULT_CATEGORY_CATALOG)
    with st.expander('Catálogo oficial de categorias', expanded=False):
        st.text_area('Uma categoria por linha', height=210, key=CATEGORY_CATALOG_KEY, help='Este catálogo define o nome final correto que será enviado/criado no Bling.')

    analyzed, stats = classify_dataframe(df, category_catalog=_catalog())
    st.session_state[CATEGORY_ANALYZED_KEY] = analyzed
    st.session_state[CATEGORY_STATS_KEY] = stats

    if not category_conference_ready():
        ok, blocked_rows, applied_count, _corrected = _apply_or_block(analyzed, source_key, stats=stats)
        if not ok:
            _render_blocked(blocked_rows, analyzed)
            return
        st.success(f'Categorização aplicada automaticamente: {applied_count} categoria(s) corrigida(s)/padronizada(s). 100% dos produtos têm categoria final válida.')
        st.rerun()

    total = int(stats.get('total', len(df)) or len(df))
    sem_categoria = int(stats.get('sem_categoria', 0) or 0)
    corrigir = int(stats.get('corrigir', 0) or 0)
    revisar = int(stats.get('revisar', 0) or 0)
    criar_vincular = int(stats.get('criar_vincular', 0) or 0)
    st.caption(f'Resumo: {total} produto(s) · sem categoria: {sem_categoria} · corrigir: {corrigir} · criar/vincular: {criar_vincular} · revisar: {revisar}')

    _render_category_review_grid(analyzed, df, source_key)

    if category_conference_ready():
        if st.button('🔄 Refazer categorização automática', use_container_width=True, key=CATEGORY_REBUILD_BUTTON_KEY):
            _clear_category_decision_state(reason='rebuild_button_clicked')
            st.rerun()

    if category_conference_was_skipped():
        st.warning('Conferência pulada porque a categorização foi desligada antes de entrar no painel.')
    elif category_conference_ready():
        st.success('Conferência confirmada. O envio ao Bling usará a categoria corrigida nesta prévia.')
    else:
        st.info('Sistema aplicando categorias automaticamente. Se alguma categoria não for segura, a etapa será bloqueada.')


__all__ = [
    'CATEGORY_DATASET_SIGNATURE_KEY', 'CATEGORY_DONE_KEY', 'CATEGORY_SKIP_KEY', 'CATEGORY_VALUES_SIGNATURE_KEY',
    'category_values_signature', 'category_conference_ready', 'category_conference_was_skipped', 'render_category_conference_step',
]
