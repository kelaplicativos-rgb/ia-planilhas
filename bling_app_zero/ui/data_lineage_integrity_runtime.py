from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/data_lineage_integrity_runtime.py'
RUNTIME_VERSION = 'data_lineage_integrity_v1_no_block_no_autofix'
TRACE_STATE_KEY = 'mapeiaai_data_lineage_integrity_trace_v1'
ORIGIN_REF_PREFIX = 'origem::'
MODEL_REF_PREFIX = 'modelo::'
FIXED_VALUE_PREFIX = '__mapeiaai_fixed_value__:'
BLANKS = {'', 'nan', 'none', 'null', '<na>'}
KEY_CANDIDATES = ('Codigo', 'Código', 'SKU', 'Referencia', 'Referência', 'IdProduto', 'ID Produto', 'ID na Loja', 'GTIN', 'EAN', 'Link Externo', 'Nome')
MAX_RECORDS = 500


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in text).split())


def _compact(value: object) -> str:
    return ''.join(ch for ch in _norm(value) if ch.isalnum())


def _value(value: object) -> str:
    text = str(value if value is not None else '').strip()
    return '' if text.casefold() in BLANKS else text


def _has_value(value: object) -> bool:
    return bool(_value(value))


def _short(value: object, limit: int = 180) -> str:
    text = _value(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def _split_ref(value: object) -> tuple[str, str]:
    text = str(value or '').strip()
    if text.startswith(ORIGIN_REF_PREFIX):
        return 'origem', text[len(ORIGIN_REF_PREFIX):].strip()
    if text.startswith(MODEL_REF_PREFIX):
        return 'modelo', text[len(MODEL_REF_PREFIX):].strip()
    if text.startswith(FIXED_VALUE_PREFIX):
        return 'fixo', text[len(FIXED_VALUE_PREFIX):].strip()
    return ('origem', text) if text else ('vazio', '')


def _column_by_compact(df: Any) -> dict[str, str]:
    if not isinstance(df, pd.DataFrame):
        return {}
    return {_compact(column): str(column) for column in df.columns}


def _actual_column(df: Any, column: object) -> str:
    if not isinstance(df, pd.DataFrame):
        return ''
    text = str(column or '').strip()
    if text in df.columns:
        return text
    return _column_by_compact(df).get(_compact(text), '')


def _row_label(row: pd.Series) -> dict[str, str]:
    out: dict[str, str] = {}
    columns = _column_by_compact(pd.DataFrame(columns=list(row.index)))
    for name in KEY_CANDIDATES:
        actual = columns.get(_compact(name), '')
        if actual:
            val = _value(row.get(actual, ''))
            if val:
                out[str(name)] = val
    return out


def _common_keys(left: pd.DataFrame, right: pd.DataFrame) -> list[tuple[str, str]]:
    if not isinstance(left, pd.DataFrame) or not isinstance(right, pd.DataFrame):
        return []
    right_cols = _column_by_compact(right)
    pairs: list[tuple[str, str]] = []
    for preferred in KEY_CANDIDATES:
        key = _compact(preferred)
        left_col = next((str(col) for col in left.columns if _compact(col) == key), '')
        right_col = right_cols.get(key, '')
        if left_col and right_col and (left_col, right_col) not in pairs:
            pairs.append((left_col, right_col))
    for left_col in left.columns:
        right_col = right_cols.get(_compact(left_col), '')
        if right_col and (str(left_col), right_col) not in pairs:
            pairs.append((str(left_col), right_col))
    return pairs


def _find_row(reference: pd.DataFrame, output: pd.DataFrame, out_row: pd.Series) -> pd.Series | None:
    if not isinstance(reference, pd.DataFrame) or reference.empty:
        return None
    ref = reference.fillna('')
    for out_col, ref_col in _common_keys(output, ref):
        wanted = _compact(out_row.get(out_col, ''))
        if not wanted:
            continue
        try:
            matches = ref[ref[ref_col].fillna('').astype(str).map(_compact) == wanted]
        except Exception:
            continue
        if not matches.empty:
            return matches.iloc[0]
    return None


def _mapped_selection(mapping: Mapping[str, str] | None, target_column: str) -> tuple[str, str]:
    data = dict(mapping or {})
    selected = data.get(target_column, '')
    if not selected:
        for key, value in data.items():
            if _compact(key) == _compact(target_column):
                selected = value
                break
    return _split_ref(selected)


def _output_col(output: pd.DataFrame, column: str) -> str:
    return _actual_column(output, column)


def _append(records: list[dict[str, str]], **kwargs: object) -> None:
    if len(records) >= MAX_RECORDS:
        return
    records.append({key: _short(value, 260) for key, value in kwargs.items()})


def _trace_mapped_fields(source: pd.DataFrame, model: pd.DataFrame, output: pd.DataFrame, mapping: Mapping[str, str] | None, records: list[dict[str, str]]) -> None:
    for out_index, out_row in output.fillna('').iterrows():
        src_row = _find_row(source, output, out_row)
        model_row = _find_row(model, output, out_row)
        label = _row_label(out_row)
        for target in [str(col) for col in output.columns]:
            kind, selected = _mapped_selection(mapping, target)
            if kind not in {'origem', 'modelo', 'fixo'} or not selected:
                continue
            final_value = _value(out_row.get(target, ''))
            ref_row = src_row if kind == 'origem' else model_row
            if kind == 'fixo':
                source_value = selected
                source_found = True
            else:
                source_col = _actual_column(source if kind == 'origem' else model, selected)
                source_found = ref_row is not None and bool(source_col)
                source_value = _value(ref_row.get(source_col, '')) if source_found else ''
            if _has_value(source_value) and not _has_value(final_value):
                _append(records, tipo='valor_mapeado_nao_chegou_na_saida', origem_do_valor=kind, campo_final=target, campo_referencia=selected, valor_referencia=source_value, valor_final=final_value, linha_final=int(out_index) + 1, identificacao=label, detalhe='O valor existia no lado escolhido pelo mapeamento, mas saiu vazio na planilha final.')
            elif _has_value(source_value) and _has_value(final_value) and str(source_value).strip() != str(final_value).strip():
                _append(records, tipo='valor_mapeado_diferente_na_saida', origem_do_valor=kind, campo_final=target, campo_referencia=selected, valor_referencia=source_value, valor_final=final_value, linha_final=int(out_index) + 1, identificacao=label, detalhe='O valor chegou diferente do valor do lado escolhido. Pode ser regra, formatação ou perda no merge.')
            elif kind in {'origem', 'modelo'} and selected and not source_found:
                _append(records, tipo='linha_ou_coluna_referencia_nao_localizada', origem_do_valor=kind, campo_final=target, campo_referencia=selected, valor_referencia='', valor_final=final_value, linha_final=int(out_index) + 1, identificacao=label, detalhe='O mapeamento aponta para uma origem/modelo, mas a linha ou coluna não foi localizada para conferência.')


def _trace_unmapped_reference_values(reference: pd.DataFrame, output: pd.DataFrame, records: list[dict[str, str]], side: str) -> None:
    if not isinstance(reference, pd.DataFrame) or reference.empty or not isinstance(output, pd.DataFrame) or output.empty:
        return
    output_cols = _column_by_compact(output)
    missing_columns = [str(col) for col in reference.columns if _compact(col) not in output_cols]
    for column in missing_columns[:80]:
        try:
            count_values = int(reference[column].fillna('').astype(str).map(_has_value).sum())
        except Exception:
            count_values = 0
        if count_values > 0:
            _append(records, tipo='coluna_com_dados_fora_da_saida_final', origem_do_valor=side, campo_final='', campo_referencia=column, valor_referencia=f'{count_values} linha(s) com valor', valor_final='', linha_final='', identificacao='', detalhe='A coluna existe no lado de referência e tem dados, mas não existe na saída final. Isso pode ser esperado se o usuário não quis essa coluna, mas fica rastreado.')


def _trace_unmatched_rows(reference: pd.DataFrame, output: pd.DataFrame, records: list[dict[str, str]], side: str) -> None:
    if not isinstance(reference, pd.DataFrame) or reference.empty or not isinstance(output, pd.DataFrame) or output.empty:
        return
    pairs = _common_keys(output, reference)
    if not pairs:
        _append(records, tipo='sem_chave_para_conferir_linhas', origem_do_valor=side, campo_final='', campo_referencia='', valor_referencia=f'{len(reference)} linha(s)', valor_final=f'{len(output)} linha(s)', linha_final='', identificacao='', detalhe='Não há chave comum segura para conferir se todas as linhas foram preservadas.')
        return
    out_col, ref_col = pairs[0]
    try:
        output_keys = set(output[out_col].fillna('').astype(str).map(_compact).tolist())
        missing = reference[~reference[ref_col].fillna('').astype(str).map(_compact).isin(output_keys)]
    except Exception:
        return
    for idx, row in missing.head(80).iterrows():
        if any(_has_value(row.get(col, '')) for col in reference.columns):
            _append(records, tipo='linha_referencia_nao_encontrada_na_saida', origem_do_valor=side, campo_final=out_col, campo_referencia=ref_col, valor_referencia=_value(row.get(ref_col, '')), valor_final='', linha_final='', identificacao=_row_label(row), detalhe='Existe uma linha com dados na referência que não foi localizada na saída final pela chave comum.')


def _build_integrity_trace(source: pd.DataFrame, model: pd.DataFrame, output: pd.DataFrame, mapping: Mapping[str, str] | None) -> pd.DataFrame:
    if not isinstance(output, pd.DataFrame) or output.empty:
        return pd.DataFrame()
    src = source.copy().fillna('') if isinstance(source, pd.DataFrame) else pd.DataFrame()
    mdl = model.copy().fillna('') if isinstance(model, pd.DataFrame) else pd.DataFrame()
    out = output.copy().fillna('')
    records: list[dict[str, str]] = []
    _trace_mapped_fields(src, mdl, out, mapping, records)
    _trace_unmapped_reference_values(src, out, records, 'origem')
    _trace_unmapped_reference_values(mdl, out, records, 'modelo')
    _trace_unmatched_rows(src, out, records, 'origem')
    _trace_unmatched_rows(mdl, out, records, 'modelo')
    return pd.DataFrame(records)


def _render_trace(trace: pd.DataFrame, *, key_prefix: str) -> None:
    st.session_state[TRACE_STATE_KEY] = trace.copy() if isinstance(trace, pd.DataFrame) else pd.DataFrame()
    if not isinstance(trace, pd.DataFrame) or trace.empty:
        st.success('Integridade de dados: nenhuma perda evidente detectada entre origem, modelo e saída final.')
        return
    summary = trace['tipo'].value_counts().to_dict() if 'tipo' in trace.columns else {}
    st.warning(f'Integridade de dados: {len(trace)} ponto(s) precisam de conferência. Nada foi alterado automaticamente.')
    if summary:
        st.caption('Resumo: ' + ' · '.join(f'{key}: {value}' for key, value in summary.items()))
    with st.expander('Ver rastreabilidade origem + modelo + saída', expanded=True):
        st.caption('Este relatório é universal: não bloqueia, não corrige e não depende de software específico.')
        st.dataframe(trace.head(200), use_container_width=True, hide_index=True)
        csv = trace.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button('⬇️ Baixar rastreabilidade de integridade', data=csv, file_name='mapeiaai_integridade_origem_modelo_saida.csv', mime='text/csv; charset=utf-8', use_container_width=True, key=f'{key_prefix}_data_lineage_integrity_download')


def install_data_lineage_integrity_runtime() -> None:
    try:
        from bling_app_zero.ui import shared_final_csv
    except Exception as exc:
        add_audit_event('data_lineage_integrity_import_failed', area='INTEGRIDADE', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return
    original_render = getattr(shared_final_csv, '_mapeiaai_original_render_shared_final_csv_for_integrity', None) or shared_final_csv.render_shared_final_csv
    setattr(shared_final_csv, '_mapeiaai_original_render_shared_final_csv_for_integrity', original_render)
    if not getattr(shared_final_csv.render_shared_final_csv, '_mapeiaai_data_lineage_integrity_wrapped', False):
        def render_shared_final_csv_with_integrity(source, contract, mapping, *, key_prefix='mapeiaai_shared_final', file_name='mapeiaai_planilha_final_mapeada.csv', run_smart_features=True, smart_rules_config=None):
            output = original_render(source, contract, mapping, key_prefix=key_prefix, file_name=file_name, run_smart_features=run_smart_features, smart_rules_config=smart_rules_config)
            try:
                trace = _build_integrity_trace(source, contract, output, mapping) if isinstance(output, pd.DataFrame) else pd.DataFrame()
                _render_trace(trace, key_prefix=key_prefix)
                add_audit_event('data_lineage_integrity_reported', area='INTEGRIDADE', status='OK' if trace.empty else 'AVISO', details={'rows': int(len(trace)), 'no_block': True, 'no_autofix': True, 'version': RUNTIME_VERSION, 'responsible_file': RESPONSIBLE_FILE})
            except Exception as exc:
                add_audit_event('data_lineage_integrity_failed', area='INTEGRIDADE', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
            return output
        render_shared_final_csv_with_integrity._mapeiaai_data_lineage_integrity_wrapped = True
        shared_final_csv.render_shared_final_csv = render_shared_final_csv_with_integrity
    add_audit_event('data_lineage_integrity_runtime_installed', area='INTEGRIDADE', status='OK', details={'version': RUNTIME_VERSION, 'universal': True, 'no_block': True, 'no_autofix': True, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_data_lineage_integrity_runtime']
