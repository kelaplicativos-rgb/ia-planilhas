from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/price_loss_trace_runtime.py'
TRACE_VERSION = 'price_loss_trace_v1_diagnostico_sem_bloqueio'
TRACE_STATE_KEY = 'mapeiaai_price_loss_trace_v1'
TRACE_SOURCE_COLUMNS_KEY = 'mapeiaai_price_loss_trace_source_price_columns_v1'
ORIGIN_REF_PREFIX = 'origem::'
MODEL_REF_PREFIX = 'modelo::'
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'
PRICE_TARGET_NAMES = ('Preco', 'Preço', 'Preco Promocional', 'Preço Promocional')
KEY_CANDIDATES = ('Código', 'Codigo', 'SKU', 'Referência', 'Referencia', 'IdProduto', 'ID Produto', 'ID na Loja', 'Link Externo', 'Nome')


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in text).split())


def _compact(value: object) -> str:
    return ''.join(ch for ch in _norm(value) if ch.isalnum())


def _split_ref(value: object) -> tuple[str, str]:
    text = str(value or '').strip()
    if text.startswith(ORIGIN_REF_PREFIX):
        return 'origem', text[len(ORIGIN_REF_PREFIX):].strip()
    if text.startswith(MODEL_REF_PREFIX):
        return 'modelo', text[len(MODEL_REF_PREFIX):].strip()
    if text.startswith(FIXED_VALUE_PREFIX):
        return 'fixo', text[len(FIXED_VALUE_PREFIX):].strip()
    return ('origem', text) if text else ('vazio', '')


def _parse_price(value: object) -> float | None:
    raw = str(value or '').strip().lower().replace('\xa0', ' ')
    if raw in {'', '0', '0.0', '0.00', '0,0', '0,00', 'r$0', 'r$0,00', 'nan', 'none', 'null', '<na>'}:
        return None
    cleaned = ''.join(ch for ch in raw if ch.isdigit() or ch in ',.-')
    if not cleaned or cleaned in {'-', ',', '.', '-,', '-.'}:
        return None
    if ',' in cleaned and '.' in cleaned:
        cleaned = cleaned.replace('.', '').replace(',', '.') if cleaned.rfind(',') > cleaned.rfind('.') else cleaned.replace(',', '')
    elif ',' in cleaned:
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif cleaned.count('.') > 1:
        parts = cleaned.split('.')
        cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
    try:
        number = float(cleaned)
    except Exception:
        return None
    return number if number > 0 else None


def _has_price(value: object) -> bool:
    return _parse_price(value) is not None


def _looks_like_price_column(column: object) -> bool:
    token = _norm(column)
    compact = _compact(column)
    if not token:
        return False
    blocked = ('custo', 'cost', 'frete', 'desconto', 'margem', 'imposto', 'taxa', 'fornecedor')
    if any(term in token for term in blocked):
        return False
    if compact in {'preco', 'precofinal', 'precodevenda', 'precovenda', 'valor', 'valorvenda', 'price', 'saleprice', 'precopromocional', 'precopromo'}:
        return True
    return 'preco' in token or token in {'valor', 'valor venda'}


def _price_columns(df: Any) -> list[str]:
    if not isinstance(df, pd.DataFrame):
        return []
    columns = [str(column) for column in df.columns if _looks_like_price_column(column)]
    regular = [column for column in columns if 'promo' not in _norm(column) and 'promocional' not in _norm(column)]
    promo = [column for column in columns if column not in regular]
    return list(dict.fromkeys([*regular, *promo]))


def _target_price_columns(df: Any) -> list[str]:
    if not isinstance(df, pd.DataFrame):
        return []
    by_compact = {_compact(column): str(column) for column in df.columns}
    out: list[str] = []
    for name in PRICE_TARGET_NAMES:
        actual = by_compact.get(_compact(name))
        if actual and actual not in out:
            out.append(actual)
    return out or _price_columns(df)


def _row_value(row: pd.Series, names: tuple[str, ...]) -> str:
    by_compact = {_compact(column): column for column in row.index}
    for name in names:
        actual = by_compact.get(_compact(name))
        if actual is None:
            continue
        value = str(row.get(actual, '') or '').strip()
        if value and value.lower() not in {'nan', 'none', 'null'}:
            return value
    return ''


def _common_key_columns(output: pd.DataFrame, source: pd.DataFrame) -> list[tuple[str, str]]:
    source_by_key = {_compact(column): str(column) for column in source.columns}
    out: list[tuple[str, str]] = []
    for preferred in KEY_CANDIDATES:
        key = _compact(preferred)
        out_col = next((str(col) for col in output.columns if _compact(col) == key), '')
        src_col = source_by_key.get(key, '')
        if out_col and src_col and (out_col, src_col) not in out:
            out.append((out_col, src_col))
    for out_col in output.columns:
        src_col = source_by_key.get(_compact(out_col), '')
        if src_col and (str(out_col), src_col) not in out:
            out.append((str(out_col), src_col))
    return out


def _find_source_row(source: pd.DataFrame, output: pd.DataFrame, out_row: pd.Series) -> pd.Series | None:
    if not isinstance(source, pd.DataFrame) or source.empty:
        return None
    frame = source.fillna('')
    for out_col, src_col in _common_key_columns(output, frame):
        wanted = _compact(out_row.get(out_col, ''))
        if not wanted:
            continue
        try:
            matches = frame[frame[src_col].fillna('').astype(str).map(_compact) == wanted]
        except Exception:
            continue
        if not matches.empty:
            return matches.iloc[0]
    return None


def _mapped_source_for_target(mapping: Mapping[str, str] | None, target_column: str) -> tuple[str, str]:
    data = dict(mapping or {})
    selected = data.get(target_column, '')
    if not selected:
        for key, value in data.items():
            if _compact(key) == _compact(target_column):
                selected = value
                break
    return _split_ref(selected)


def _valid_prices_in_row(row: pd.Series | None, columns: list[str]) -> dict[str, str]:
    if row is None:
        return {}
    out: dict[str, str] = {}
    for column in columns:
        if column in row.index and _has_price(row.get(column, '')):
            out[column] = str(row.get(column, '') or '').strip()
    return out


def _operation_is_price_update(output: pd.DataFrame) -> bool:
    values = []
    for key in ('operation', 'selected_operation', 'bling_operation', 'flow_operation', 'operacao_final', 'tipo_operacao_final', 'final_download_operation', 'df_final_download_operation', 'api_operation', 'bling_api_operation'):
        values.append(str(st.session_state.get(key) or '').strip())
    if 'atualizacao_preco' in values:
        return True
    columns = {_compact(column) for column in output.columns} if isinstance(output, pd.DataFrame) else set()
    return 'preco' in columns and ('codigo' in columns or 'idproduto' in columns or 'idnaloja' in columns)


def _trace_price_loss(source: pd.DataFrame, output: pd.DataFrame, mapping: Mapping[str, str] | None) -> pd.DataFrame:
    if not isinstance(output, pd.DataFrame) or output.empty or not _operation_is_price_update(output):
        return pd.DataFrame()
    out = output.copy().fillna('')
    src = source.copy().fillna('') if isinstance(source, pd.DataFrame) else pd.DataFrame()
    target_price_cols = _target_price_columns(out)
    source_price_cols = _price_columns(src)
    st.session_state[TRACE_SOURCE_COLUMNS_KEY] = source_price_cols
    records: list[dict[str, str]] = []
    if not target_price_cols:
        return pd.DataFrame([{'status': 'sem_coluna_preco_final', 'onde_perdeu': 'modelo_saida_final', 'detalhe': 'A saída final não tem coluna de preço detectável.'}])

    for idx, row in out.iterrows():
        final_prices = {column: str(row.get(column, '') or '').strip() for column in target_price_cols}
        if any(_has_price(value) for value in final_prices.values()):
            continue
        src_row = _find_source_row(src, out, row)
        source_valid_prices = _valid_prices_in_row(src_row, source_price_cols)
        mapped_details: list[str] = []
        mapped_had_price = False
        mapped_missing = False
        mapped_model = False
        for target_col in target_price_cols:
            kind, selected_col = _mapped_source_for_target(mapping, target_col)
            if kind == 'modelo':
                mapped_model = True
            if kind == 'origem' and selected_col:
                if src_row is not None and selected_col in src_row.index:
                    value = str(src_row.get(selected_col, '') or '').strip()
                    mapped_details.append(f'{target_col} <= origem::{selected_col} ({value or "vazio"})')
                    if _has_price(value):
                        mapped_had_price = True
                else:
                    mapped_missing = True
                    mapped_details.append(f'{target_col} <= origem::{selected_col} (coluna/linha não localizada)')
            elif kind == 'fixo':
                mapped_details.append(f'{target_col} <= valor fixo ({selected_col})')
                if _has_price(selected_col):
                    mapped_had_price = True
            elif kind == 'modelo':
                mapped_details.append(f'{target_col} <= modelo::{selected_col}')
            else:
                mapped_details.append(f'{target_col} sem mapeamento')

        if src_row is None:
            where = 'nao_localizou_linha_da_origem'
            status = 'sem_preco_final_e_sem_linha_origem_para_comparar'
        elif mapped_had_price:
            where = 'saida_final_ou_merge'
            status = 'preco_existia_na_coluna_mapeada_mas_saida_final_zerou'
        elif source_valid_prices:
            where = 'mapeamento'
            status = 'origem_tinha_preco_em_outra_coluna_mas_mapeamento_nao_usou'
        elif mapped_model:
            where = 'modelo_preservado'
            status = 'preco_final_veio_do_modelo_ou_preservacao_sem_preco'
        elif mapped_missing:
            where = 'mapeamento_linha_coluna'
            status = 'mapeamento_apontou_para_origem_mas_coluna_ou_linha_nao_foi_localizada'
        else:
            where = 'captura_site_origem'
            status = 'produto_ja_chegou_da_origem_sem_preco_valido'

        records.append(
            {
                'status': status,
                'onde_perdeu': where,
                'linha_final': str(int(idx) + 1),
                'IdProduto': _row_value(row, ('IdProduto', 'ID Produto', 'id produto')),
                'Código': _row_value(row, ('Código', 'Codigo', 'SKU', 'Referência')),
                'Nome': _row_value(row, ('Nome', 'Produto', 'Descrição', 'Descricao')),
                'Link Externo': _row_value(row, ('Link Externo', 'URL', 'Link')),
                'precos_finais': ' | '.join(f'{k}={v or "vazio"}' for k, v in final_prices.items()),
                'mapeamento_preco': ' | '.join(mapped_details),
                'precos_validos_na_origem': ' | '.join(f'{k}={v}' for k, v in source_valid_prices.items()),
                'colunas_preco_origem_detectadas': ', '.join(source_price_cols),
            }
        )
    return pd.DataFrame(records)


def _render_trace(trace: pd.DataFrame, *, key_prefix: str) -> None:
    st.session_state[TRACE_STATE_KEY] = trace.copy() if isinstance(trace, pd.DataFrame) else pd.DataFrame()
    if not isinstance(trace, pd.DataFrame) or trace.empty:
        return
    summary = trace['onde_perdeu'].value_counts().to_dict() if 'onde_perdeu' in trace.columns else {}
    st.warning(f'Rastreamento de preço: {len(trace)} produto(s) estão sem preço válido na saída final. Nada foi alterado automaticamente.')
    if summary:
        st.caption('Resumo provável: ' + ' · '.join(f'{key}: {value}' for key, value in summary.items()))
    with st.expander('Ver onde o preço se perdeu', expanded=True):
        st.dataframe(trace.head(120), use_container_width=True, hide_index=True)
        csv = trace.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button('⬇️ Baixar rastreamento de preços', data=csv, file_name='mapeiaai_rastreamento_preco.csv', mime='text/csv; charset=utf-8', use_container_width=True, key=f'{key_prefix}_price_loss_trace_download')


def install_price_loss_trace_runtime() -> None:
    try:
        from bling_app_zero.ui import shared_final_csv
    except Exception as exc:
        add_audit_event('price_loss_trace_runtime_import_failed', area='PRECO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    original_render = getattr(shared_final_csv, '_mapeiaai_original_render_shared_final_csv_for_price_trace', None) or shared_final_csv.render_shared_final_csv
    setattr(shared_final_csv, '_mapeiaai_original_render_shared_final_csv_for_price_trace', original_render)
    if not getattr(shared_final_csv.render_shared_final_csv, '_mapeiaai_price_trace_wrapped', False):
        def render_shared_final_csv_with_price_trace(source, contract, mapping, *, key_prefix='mapeiaai_shared_final', file_name='mapeiaai_planilha_final_mapeada.csv', run_smart_features=True, smart_rules_config=None):
            output = original_render(source, contract, mapping, key_prefix=key_prefix, file_name=file_name, run_smart_features=run_smart_features, smart_rules_config=smart_rules_config)
            try:
                trace = _trace_price_loss(source, output, mapping) if isinstance(output, pd.DataFrame) else pd.DataFrame()
                _render_trace(trace, key_prefix=key_prefix)
                if isinstance(trace, pd.DataFrame) and not trace.empty:
                    add_audit_event('price_loss_trace_runtime_reported', area='PRECO', status='AVISO', details={'rows': int(len(trace)), 'summary': trace['onde_perdeu'].value_counts().to_dict() if 'onde_perdeu' in trace.columns else {}, 'responsible_file': RESPONSIBLE_FILE})
            except Exception as exc:
                add_audit_event('price_loss_trace_runtime_failed', area='PRECO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
            return output
        render_shared_final_csv_with_price_trace._mapeiaai_price_trace_wrapped = True
        shared_final_csv.render_shared_final_csv = render_shared_final_csv_with_price_trace

    original_preview = getattr(shared_final_csv, '_mapeiaai_original_render_final_csv_preview_for_price_trace', None) or shared_final_csv.render_final_csv_preview
    setattr(shared_final_csv, '_mapeiaai_original_render_final_csv_preview_for_price_trace', original_preview)
    if not getattr(shared_final_csv.render_final_csv_preview, '_mapeiaai_price_trace_wrapped', False):
        def render_final_csv_preview_with_price_trace(df_final, *, key_prefix='mapeiaai_final_csv'):
            output = original_preview(df_final, key_prefix=key_prefix)
            try:
                trace = _trace_price_loss(pd.DataFrame(), output, {}) if isinstance(output, pd.DataFrame) else pd.DataFrame()
                _render_trace(trace, key_prefix=key_prefix)
            except Exception as exc:
                add_audit_event('price_loss_trace_preview_failed', area='PRECO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
            return output
        render_final_csv_preview_with_price_trace._mapeiaai_price_trace_wrapped = True
        shared_final_csv.render_final_csv_preview = render_final_csv_preview_with_price_trace

    add_audit_event('price_loss_trace_runtime_installed', area='PRECO', status='OK', details={'version': TRACE_VERSION, 'no_price_change': True, 'no_block': True, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_price_loss_trace_runtime']
