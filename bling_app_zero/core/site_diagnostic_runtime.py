from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, Mapping

import streamlit as st

from bling_app_zero.core.audit import get_audit_events

RESPONSIBLE_FILE = 'bling_app_zero/core/site_diagnostic_runtime.py'
SITE_CAPTURE_STATE_KEY = 'neutral_site_capture_state_v1'
SITE_CAPTURE_REPORT_KEY = 'neutral_site_capture_report_v1'
SITE_TRACE_KEYS = (
    'site_discovery_trace_v1',
    'site_capture_trace_v1',
    'site_progress_trace_v1',
    'deep_site_capture_trace_v1',
    'fast_site_scraper_trace_v1',
)
SITE_SCALAR_KEYS = (
    'site_capture_status',
    'site_capture_message',
    'site_capture_rows',
    'site_url',
    'url_site',
    'frontpage_site_url',
    'home_slim_site_url',
)
SITE_DF_PREFIXES = (
    'df_site_',
    'df_origem_site_',
)
SITE_DF_EXACT_KEYS = {
    'df_site_bruto',
    'df_origem_site_como_planilha',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_atualizacao_preco',
    'df_site_bruto_preco',
    'df_site_bruto_universal',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha_atualizacao_preco',
    'df_origem_site_como_planilha_preco',
    'df_origem_site_como_planilha_universal',
}


def _shape(value: Any) -> tuple[int, int]:
    shape = getattr(value, 'shape', None)
    if isinstance(shape, tuple) and len(shape) >= 2:
        return int(shape[0] or 0), int(shape[1] or 0)
    columns = getattr(value, 'columns', None)
    if columns is not None:
        try:
            return len(value), len(columns)
        except Exception:
            return 0, 0
    if isinstance(value, list):
        if value and isinstance(value[0], Mapping):
            keys: set[str] = set()
            for row in value:
                keys.update(str(key) for key in dict(row).keys())
            return len(value), len(keys)
        return len(value), 0
    return 0, 0


def _columns(value: Any) -> list[str]:
    columns = getattr(value, 'columns', None)
    if columns is not None:
        try:
            return [str(column) for column in list(columns)[:120]]
        except Exception:
            return []
    if isinstance(value, list) and value and isinstance(value[0], Mapping):
        keys: list[str] = []
        for row in value:
            for key in dict(row).keys():
                text = str(key)
                if text not in keys:
                    keys.append(text)
        return keys[:120]
    return []


def _safe_preview(value: Any, *, max_items: int = 20) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _safe_preview(item, max_items=max_items) for key, item in dict(value).items() if not _looks_sensitive(key)}
    if isinstance(value, list):
        return [_safe_preview(item, max_items=max_items) for item in value[:max_items]]
    if isinstance(value, tuple):
        return [_safe_preview(item, max_items=max_items) for item in value[:max_items]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = str(value) if isinstance(value, str) else value
        if isinstance(text, str) and len(text) > 600:
            return text[:600] + '...'
        return text
    return str(type(value).__name__)


def _looks_sensitive(key: Any) -> bool:
    text = str(key or '').strip().lower()
    return any(part in text for part in ('senha', 'password', 'secret', 'token', 'authorization', 'cookie', 'credential'))


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode('utf-8')


def _csv_bytes(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, '') for field in fieldnames})
    return buffer.getvalue().encode('utf-8-sig')


def _audit_site_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for event in get_audit_events():
        if not isinstance(event, Mapping):
            continue
        area = str(event.get('area') or '').upper()
        action = str(event.get('action') or '').lower()
        details = event.get('details') if isinstance(event.get('details'), Mapping) else {}
        responsible = str(dict(details).get('responsible_file') or '').lower()
        if area == 'SITE' or action.startswith('site_') or 'site_capture' in action or 'site_scraper' in responsible or 'site_capture' in responsible:
            events.append(dict(event))
    return events[-250:]


def _session_site_scalars() -> dict[str, Any]:
    scalars: dict[str, Any] = {}
    for key in SITE_SCALAR_KEYS:
        if key in st.session_state:
            scalars[key] = _safe_preview(st.session_state.get(key))
    for key, value in list(st.session_state.items()):
        text = str(key or '')
        lower = text.lower()
        if text in scalars or _looks_sensitive(text):
            continue
        if 'site' not in lower:
            continue
        if not any(part in lower for part in ('capture', 'crawler', 'scraper', 'progress', 'trace', 'report', 'url', 'produto', 'product', 'rows', 'status', 'message')):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            scalars[text] = _safe_preview(value)
    return scalars


def _collect_trace_from_state() -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for key in SITE_TRACE_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, list):
            for index, item in enumerate(value[-500:], start=1):
                if isinstance(item, Mapping):
                    row = dict(item)
                    row.setdefault('source_key', key)
                    row.setdefault('trace_index', index)
                    trace.append(row)
                else:
                    trace.append({'source_key': key, 'trace_index': index, 'value': str(item)[:600]})
    for key, value in list(st.session_state.items()):
        text = str(key or '')
        lower = text.lower()
        if text in SITE_TRACE_KEYS or _looks_sensitive(text):
            continue
        if not isinstance(value, list) or not value:
            continue
        if 'site' not in lower or not any(part in lower for part in ('trace', 'progress', 'event', 'log')):
            continue
        for index, item in enumerate(value[-500:], start=1):
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault('source_key', text)
                row.setdefault('trace_index', index)
                trace.append(row)
    return trace[-800:]


def _site_dataframe_summary() -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for key, value in list(st.session_state.items()):
        text = str(key or '')
        if text not in SITE_DF_EXACT_KEYS and not text.startswith(SITE_DF_PREFIXES):
            continue
        rows, cols = _shape(value)
        if rows <= 0 and cols <= 0:
            continue
        summary.append({'state_key': text, 'rows': rows, 'columns_count': cols, 'columns': _columns(value)})
    return summary


def _extract_numeric(value: Any, path: tuple[str, ...]) -> int:
    current = value
    for part in path:
        if not isinstance(current, Mapping):
            return 0
        current = current.get(part)
    try:
        return int(current or 0)
    except Exception:
        return 0


def _max_from_trace(trace: list[dict[str, Any]], *keys: str) -> int:
    best = 0
    for row in trace:
        for key in keys:
            try:
                best = max(best, int(row.get(key) or 0))
            except Exception:
                pass
    return best


def _compare_site_pipeline(state: Any, report: Any, trace: list[dict[str, Any]], dfs: list[dict[str, Any]]) -> dict[str, Any]:
    report_rows = _extract_numeric(report, ('rows',)) if isinstance(report, Mapping) else 0
    result_rows = _extract_numeric(state, ('result', 'rows')) if isinstance(state, Mapping) else 0
    progress_rows = _extract_numeric(state, ('progress', 'rows')) if isinstance(state, Mapping) else 0
    trace_products = _max_from_trace(trace, 'found_products', 'urls_found', 'rows')
    trace_visited = _max_from_trace(trace, 'visited_pages')
    trace_scanned = _max_from_trace(trace, 'scanned_pages', 'processed')
    site_df_rows = max([int(item.get('rows') or 0) for item in dfs] or [0])
    raw_df_rows = max([int(item.get('rows') or 0) for item in dfs if str(item.get('state_key') or '').startswith('df_site_')] or [0])
    origin_df_rows = max([int(item.get('rows') or 0) for item in dfs if str(item.get('state_key') or '').startswith('df_origem_site_')] or [0])

    warnings: list[str] = []
    if trace_visited == 0 and trace_scanned == 0 and site_df_rows == 0:
        warnings.append('Não há evidência de páginas visitadas nem DataFrame de site formado.')
    if trace_products > 0 and raw_df_rows == 0:
        warnings.append('Crawler encontrou URLs/produtos, mas nenhum DataFrame bruto de site foi formado.')
    if raw_df_rows > 0 and origin_df_rows == 0:
        warnings.append('DataFrame bruto existe, mas a origem de dados por site não foi formada.')
    if report_rows and site_df_rows and report_rows != site_df_rows:
        warnings.append('Quantidade reportada pela captura difere da maior base de site no session_state.')
    if result_rows and site_df_rows and result_rows != site_df_rows:
        warnings.append('Resultado da captura difere da maior base de site no session_state.')

    return {
        'report_rows': report_rows,
        'result_rows': result_rows,
        'progress_rows': progress_rows,
        'trace_found_products_or_urls': trace_products,
        'trace_visited_pages': trace_visited,
        'trace_scanned_pages': trace_scanned,
        'raw_site_dataframe_rows': raw_df_rows,
        'origin_site_dataframe_rows': origin_df_rows,
        'largest_site_dataframe_rows': site_df_rows,
        'warnings': warnings,
    }


def _trace_csv_rows(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(trace, start=1):
        rows.append({
            'index': index,
            'source_key': item.get('source_key', ''),
            'stage': item.get('stage', ''),
            'message': item.get('message', ''),
            'current_url': item.get('current_url', ''),
            'visited_pages': item.get('visited_pages', ''),
            'scanned_pages': item.get('scanned_pages', item.get('processed', '')),
            'found_products': item.get('found_products', item.get('urls_found', item.get('rows', ''))),
            'queued_pages': item.get('queued_pages', ''),
            'links_found_on_page': item.get('links_found_on_page', ''),
            'ignored_external_links': item.get('ignored_external_links', ''),
            'stop_reason': item.get('stop_reason', ''),
            'elapsed_seconds': item.get('elapsed_seconds', ''),
        })
    return rows


def collect_site_diagnostic_payload() -> dict[str, Any]:
    state = st.session_state.get(SITE_CAPTURE_STATE_KEY, {})
    report = st.session_state.get(SITE_CAPTURE_REPORT_KEY, {})
    trace = _collect_trace_from_state()
    dfs = _site_dataframe_summary()
    audit_events = _audit_site_events()
    comparison = _compare_site_pipeline(state, report, trace, dfs)
    return {
        'state_key': SITE_CAPTURE_STATE_KEY,
        'report_key': SITE_CAPTURE_REPORT_KEY,
        'capture_state': _safe_preview(state),
        'capture_report': _safe_preview(report),
        'session_site_scalars': _session_site_scalars(),
        'site_dataframe_summary': dfs,
        'site_audit_events': _safe_preview(audit_events, max_items=250),
        'site_discovery_trace': _safe_preview(trace, max_items=800),
        'pipeline_comparison': comparison,
        'diagnostic_note': 'Mostra se a falha ocorreu na busca de URLs, na extração, na formação do DataFrame bruto ou na origem final por site.',
        'responsible_file': RESPONSIBLE_FILE,
    }


def site_diagnostic_json_bytes(payload: dict[str, Any]) -> bytes:
    return _json_bytes(payload)


def site_trace_csv_bytes(payload: dict[str, Any]) -> bytes:
    trace = payload.get('site_discovery_trace') if isinstance(payload, Mapping) else []
    rows = _trace_csv_rows(trace if isinstance(trace, list) else [])
    return _csv_bytes(rows, ['index', 'source_key', 'stage', 'message', 'current_url', 'visited_pages', 'scanned_pages', 'found_products', 'queued_pages', 'links_found_on_page', 'ignored_external_links', 'stop_reason', 'elapsed_seconds'])


def site_dataframe_summary_csv_bytes(payload: dict[str, Any]) -> bytes:
    items = payload.get('site_dataframe_summary') if isinstance(payload, Mapping) else []
    rows: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        rows.append({
            'state_key': item.get('state_key', ''),
            'rows': item.get('rows', 0),
            'columns_count': item.get('columns_count', 0),
            'columns': ' | '.join(map(str, item.get('columns') or [])),
        })
    return _csv_bytes(rows, ['state_key', 'rows', 'columns_count', 'columns'])


__all__ = [
    'collect_site_diagnostic_payload',
    'site_dataframe_summary_csv_bytes',
    'site_diagnostic_json_bytes',
    'site_trace_csv_bytes',
]
