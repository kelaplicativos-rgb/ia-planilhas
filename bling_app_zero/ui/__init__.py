"""Interfaces Streamlit do BLINGCREATOR."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd
import streamlit as st

PRESERVE_MODEL_ENABLED_KEY = 'mapeiaai_preserve_model_data_enabled'
PRESERVE_MODEL_KEY_COLUMN_KEY = 'mapeiaai_preserve_model_data_key_column'
SPLIT_DOWNLOAD_LIMIT_KEY = 'mapeiaai_final_split_download_limit'
SPLIT_LIMITS = (200, 1000, 10000)


def _plain_key(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return ''.join(ch for ch in text if ch.isalnum())


def _model_has_values(df_model: Any) -> bool:
    try:
        frame = df_model.fillna('').astype(str)
        return bool(frame.apply(lambda col: col.str.strip().ne('').any()).any())
    except Exception:
        return False


def _key_options(df_model: Any) -> list[str]:
    try:
        columns = [str(column) for column in df_model.columns]
    except Exception:
        return []
    terms = ('codigo', 'sku', 'idproduto', 'idnaloja', 'gtin', 'ean', 'referencia')
    preferred = [column for column in columns if any(term in _plain_key(column) for term in terms)]
    return list(dict.fromkeys([*preferred, *columns]))


def _mapped_targets(mapping: Mapping[str, str] | None, columns: list[str]) -> set[str]:
    data = dict(mapping or {})
    return {column for column in columns if str(data.get(column, '') or '').strip()}


def _apply_model_preserve(df_source: pd.DataFrame, df_model: pd.DataFrame, mapping: Mapping[str, str] | None, original_builder: Callable[..., pd.DataFrame]) -> pd.DataFrame:
    mapped = original_builder(df_source, df_model, mapping).copy().fillna('')
    if not bool(st.session_state.get(PRESERVE_MODEL_ENABLED_KEY, False)):
        return mapped

    key_column = str(st.session_state.get(PRESERVE_MODEL_KEY_COLUMN_KEY) or '').strip()
    if not key_column or key_column not in mapped.columns:
        return mapped

    try:
        base = df_model.copy().fillna('')
    except Exception:
        return mapped
    for column in mapped.columns:
        if column not in base.columns:
            base[column] = ''
    base = base.loc[:, list(mapped.columns)].fillna('').reset_index(drop=True)
    if base.empty or key_column not in base.columns:
        return mapped

    index_by_key: dict[str, int] = {}
    for idx, value in enumerate(base[key_column].tolist()):
        key = _plain_key(value)
        if key and key not in index_by_key:
            index_by_key[key] = idx

    update_columns = _mapped_targets(mapping, list(mapped.columns))
    if not update_columns:
        return base

    out = base.copy().fillna('')
    matched = 0
    skipped = 0
    for _, row in mapped.iterrows():
        key = _plain_key(row.get(key_column, ''))
        if not key or key not in index_by_key:
            skipped += 1
            continue
        matched += 1
        model_row = index_by_key[key]
        for column in update_columns:
            out.at[model_row, column] = '' if row.get(column) is None else str(row.get(column))

    try:
        from bling_app_zero.core.audit import add_audit_event
        add_audit_event(
            'model_data_preserve_applied',
            area='UNIVERSAL',
            status='OK',
            details={
                'rows_model': int(len(base)),
                'rows_source': int(len(mapped)),
                'matched_rows': int(matched),
                'skipped_source_rows': int(skipped),
                'key_column': key_column,
                'updated_columns': sorted(update_columns),
                'responsible_file': 'bling_app_zero/ui/__init__.py',
            },
        )
    except Exception:
        pass
    return out


def _render_model_preserve_controls(contract: pd.DataFrame, mapping: Mapping[str, str] | None, key_prefix: str) -> None:
    st.session_state.setdefault(PRESERVE_MODEL_ENABLED_KEY, False)
    st.session_state.setdefault(PRESERVE_MODEL_KEY_COLUMN_KEY, '')
    if not _model_has_values(contract):
        st.session_state[PRESERVE_MODEL_ENABLED_KEY] = False
        st.session_state[PRESERVE_MODEL_KEY_COLUMN_KEY] = ''
        return

    columns_text = ' '.join(_plain_key(column) for column in getattr(contract, 'columns', []))
    likely_update = any(term in columns_text for term in ('preco', 'promocional', 'estoque', 'saldo', 'idproduto', 'idnaloja'))
    with st.expander('Dados existentes da planilha modelo', expanded=bool(likely_update)):
        st.caption('Padrao seguro: limpar os dados da planilha modelo e usar apenas as colunas como estrutura.')
        enabled = st.toggle(
            'Preservar dados preenchidos da planilha modelo e atualizar somente produtos encontrados pela chave',
            value=False,
            key=f'{key_prefix}_preserve_model_data_toggle_v1',
            help='Use apenas em casos especificos, como atualizacao de precos, estoque ou multiloja.',
        )
        st.session_state[PRESERVE_MODEL_ENABLED_KEY] = bool(enabled)
        if not enabled:
            st.session_state[PRESERVE_MODEL_KEY_COLUMN_KEY] = ''
            st.info('Modo atual: modelo limpo. A saida final sera criada a partir da origem de dados.')
            return

        options = _key_options(contract)
        if not options:
            st.session_state[PRESERVE_MODEL_ENABLED_KEY] = False
            st.session_state[PRESERVE_MODEL_KEY_COLUMN_KEY] = ''
            st.error('Preservacao bloqueada: nenhuma coluna de chave foi encontrada no modelo.')
            return

        selected = st.selectbox('Chave para juntar modelo + origem', options, index=0, key=f'{key_prefix}_preserve_model_key_column_v1')
        st.session_state[PRESERVE_MODEL_KEY_COLUMN_KEY] = str(selected)
        if not str((mapping or {}).get(str(selected), '') or '').strip():
            st.warning(f'Mapeie a coluna "{selected}" com a chave da origem antes de montar a saida final.')
        st.warning('Com preservacao ligada, campos nao mapeados ficam como estao no modelo. Campos mapeados sao sobrescritos pela origem/calculadora.')


def _safe_stem(file_name: str | None) -> str:
    stem = Path(str(file_name or 'mapeiaai_planilha_final_mapeada.csv')).stem or 'mapeiaai_planilha_final_mapeada'
    return ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in stem).strip('_') or 'mapeiaai_planilha_final_mapeada'


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.fillna('').to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')


def _render_split_downloads(output: pd.DataFrame | None, key_prefix: str, file_name: str | None = None) -> None:
    if not isinstance(output, pd.DataFrame) or output.empty:
        return
    rows = int(len(output))
    with st.expander('Dividir download final para o Bling', expanded=rows > 200):
        st.caption('Opcional. Escolha um limite por arquivo quando precisar importar em partes.')
        labels = ['Nao dividir', '200 linhas', '1000 linhas', '10000 linhas']
        choice = st.radio('Particionar arquivo final', labels, index=0, key=f'{key_prefix}_split_download_limit_v1')
        limit = 0 if choice == labels[0] else int(choice.split()[0])
        st.session_state[SPLIT_DOWNLOAD_LIMIT_KEY] = limit
        if limit <= 0:
            st.info(f'Sem divisao: {rows} linha(s) no arquivo unico.')
            return
        if rows <= limit:
            st.success(f'{rows} linha(s): nao precisa dividir para o limite de {limit}.')
            return
        parts = [output.iloc[start:start + limit].copy() for start in range(0, rows, limit)]
        stem = _safe_stem(file_name)
        st.warning(f'{rows} linha(s): gerando {len(parts)} arquivo(s) com ate {limit} linhas.')
        for index, part in enumerate(parts, start=1):
            name = f'{stem}_parte_{index:02d}_de_{len(parts):02d}_limite_{limit}.csv'
            st.download_button(
                f'Baixar parte {index}/{len(parts)} - {len(part)} linhas',
                data=_csv_bytes(part),
                file_name=name,
                mime='text/csv; charset=utf-8',
                use_container_width=True,
                key=f'{key_prefix}_split_part_{limit}_{index}',
            )


def _install_model_data_preserve_patch() -> None:
    try:
        from bling_app_zero.core import final_output_engine
        from bling_app_zero.ui import shared_final_csv
    except Exception:
        return
    if getattr(shared_final_csv, '_mapeiaai_model_data_preserve_patched', False):
        return

    original_builder = getattr(final_output_engine, '_mapeiaai_original_build_universal_output', None) or final_output_engine.build_universal_output
    setattr(final_output_engine, '_mapeiaai_original_build_universal_output', original_builder)

    def build_universal_output_with_preserve(df_source: pd.DataFrame, df_model: pd.DataFrame, mapping: Mapping[str, str] | None = None) -> pd.DataFrame:
        return _apply_model_preserve(df_source, df_model, mapping, original_builder)

    final_output_engine.build_universal_output = build_universal_output_with_preserve

    original_render = getattr(shared_final_csv, '_mapeiaai_original_render_shared_final_csv', None) or shared_final_csv.render_shared_final_csv
    setattr(shared_final_csv, '_mapeiaai_original_render_shared_final_csv', original_render)

    def render_shared_final_csv_with_preserve(source: pd.DataFrame, contract: pd.DataFrame, mapping: dict[str, str], *args, **kwargs):
        key_prefix = str(kwargs.get('key_prefix') or 'mapeiaai_shared_final')
        file_name = str(kwargs.get('file_name') or 'mapeiaai_planilha_final_mapeada.csv')
        _render_model_preserve_controls(contract, mapping, key_prefix)
        result = original_render(source, contract, mapping, *args, **kwargs)
        _render_split_downloads(result, key_prefix, file_name)
        return result

    shared_final_csv.render_shared_final_csv = render_shared_final_csv_with_preserve
    try:
        original_preview = getattr(shared_final_csv, '_mapeiaai_original_render_final_csv_preview', None) or shared_final_csv.render_final_csv_preview
        setattr(shared_final_csv, '_mapeiaai_original_render_final_csv_preview', original_preview)

        def render_final_csv_preview_with_split(df_final: pd.DataFrame, *args, **kwargs):
            key_prefix = str(kwargs.get('key_prefix') or 'mapeiaai_final_csv')
            result = original_preview(df_final, *args, **kwargs)
            _render_split_downloads(result, key_prefix, 'mapeiaai_planilha_final_mapeada.csv')
            return result

        shared_final_csv.render_final_csv_preview = render_final_csv_preview_with_split
    except Exception:
        pass

    try:
        from bling_app_zero.ui import universal_flow
        universal_flow.render_shared_final_csv = render_shared_final_csv_with_preserve
    except Exception:
        pass
    shared_final_csv._mapeiaai_model_data_preserve_patched = True


try:
    from bling_app_zero.ui.live_operation_runtime_patch import install_live_operation_runtime_patch
    install_live_operation_runtime_patch()
except Exception:
    pass

try:
    _install_model_data_preserve_patch()
except Exception:
    pass

try:
    from bling_app_zero.ui.download_estoque_runtime_fix import install_download_estoque_runtime_fix
    install_download_estoque_runtime_fix()
except Exception:
    pass

__all__ = []
