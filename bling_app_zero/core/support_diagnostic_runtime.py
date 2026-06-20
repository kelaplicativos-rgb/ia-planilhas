from __future__ import annotations

import csv
import json
import unicodedata
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from bling_app_zero.core.audit import audit_download_payload, get_audit_events, get_audit_session_id
from bling_app_zero.core.debug import LOG_SESSION_KEY, get_debug_logs
from bling_app_zero.core.system_inventory_runtime import inventory_markdown, inventory_payload, inventory_summary

DATAFRAME_SAMPLE_MAX_ROWS = 60
DATAFRAME_SAMPLE_MAX_COLUMNS = 90

DATAFRAME_KEYS = (
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_atualizacao_preco',
    'df_site_bruto_universal',
    'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha_atualizacao_preco',
    'df_origem_site_como_planilha_universal',
    'cadastro_wizard_df_origem',
    'cadastro_wizard_df_para_mapear',
    'df_origem',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_origem_cadastro',
    'df_origem_estoque',
    'df_origem_universal',
    'df_origem_cadastro_precificada',
    'df_final_cadastro_preview_rules_applied',
    'df_final_cadastro',
    'df_final_estoque',
    'df_final_universal',
    'df_final_download',
    'df_final_download_snapshot',
)

QUALITY_CANDIDATES = {
    'descricao': ('descricao', 'descrição', 'description', 'titulo', 'título', 'title', 'nome', 'produto'),
    'marca': ('marca', 'brand', 'fabricante'),
    'categoria': ('categoria', 'category'),
    'preco': ('preco', 'preço', 'price', 'valor', 'preço unitário', 'preco unitario'),
    'imagens': ('imagens', 'imagem', 'url imagens', 'url imagem', 'foto', 'fotos', 'image', 'images'),
    'sku_codigo': ('sku', 'codigo', 'código', 'ref', 'referencia', 'referência', 'modelo', 'id produto'),
    'gtin_ean': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'barcode'),
}

SENSITIVE_COLUMN_PARTS = ('senha', 'secret', 'authorization', 'credential', 'cookie')


def _normalize(value: Any) -> str:
    text = str(value or '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    return ''.join(char for char in text if not unicodedata.combining(char))


def _safe_name(value: Any, fallback: str = 'dados') -> str:
    text = _normalize(value).replace(' ', '_')
    safe = ''.join(char if char.isalnum() or char in {'_', '-', '.'} else '_' for char in text)
    return (safe.strip('._-') or fallback)[:140]


def _log_signature(item: dict[str, Any]) -> str:
    try:
        payload = {
            'hora': item.get('hora') or item.get('timestamp'),
            'nivel': item.get('nivel') or item.get('status'),
            'origem': item.get('origem') or item.get('area'),
            'mensagem': item.get('mensagem') or item.get('action'),
            'detalhes': item.get('detalhes') or item.get('details'),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(item)[:1000]


def collect_debug_logs() -> list[dict[str, Any]]:
    """Coleta logs técnicos reais, inclusive logs namespaced do session_store v2."""
    collected: list[dict[str, Any]] = []
    try:
        collected.extend(item for item in get_debug_logs() if isinstance(item, dict))
    except Exception:
        pass

    for key, value in list(st.session_state.items()):
        text_key = str(key or '')
        if text_key != LOG_SESSION_KEY and not text_key.endswith(f':{LOG_SESSION_KEY}'):
            continue
        if isinstance(value, list):
            collected.extend(item for item in value if isinstance(item, dict))

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in collected:
        signature = _log_signature(item)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(item)
    return unique[-600:]


def _logs_to_text(logs: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in logs:
        lines.append(
            f"[{item.get('hora') or item.get('timestamp')}] "
            f"[{item.get('nivel') or item.get('status')}] "
            f"[{item.get('origem') or item.get('area')}] "
            f"{item.get('mensagem') or item.get('action') or ''}"
        )
    return '\n'.join(lines)


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode('utf-8')


def _is_dataframe_like(value: Any) -> bool:
    return bool(hasattr(value, 'shape') and hasattr(value, 'columns') and hasattr(value, 'head'))


def _should_export_dataframe(key: Any, value: Any) -> bool:
    text = str(key or '')
    if not _is_dataframe_like(value):
        return False
    if text in DATAFRAME_KEYS:
        return True
    return text.startswith(('df_', 'cadastro_wizard_df_', 'estoque_wizard_df_')) or '_df_' in text


def collect_dataframes() -> list[tuple[str, Any]]:
    dataframes: list[tuple[str, Any]] = []
    seen_ids: set[int] = set()
    for key, value in list(st.session_state.items()):
        if not _should_export_dataframe(key, value):
            continue
        identity = id(value)
        if identity in seen_ids:
            continue
        seen_ids.add(identity)
        dataframes.append((str(key), value))
    return dataframes


def _safe_dataframe_sample(value: Any) -> Any:
    sample = value.head(DATAFRAME_SAMPLE_MAX_ROWS).copy()
    try:
        sample = sample.iloc[:, :DATAFRAME_SAMPLE_MAX_COLUMNS]
    except Exception:
        pass
    for column in list(getattr(sample, 'columns', [])):
        normalized = _normalize(column)
        if any(part in normalized for part in SENSITIVE_COLUMN_PARTS):
            sample[column] = '[REDACTED]'
    return sample


def _dataframe_sample_csv_bytes(value: Any) -> bytes:
    sample = _safe_dataframe_sample(value)
    buffer = StringIO()
    sample.to_csv(buffer, index=False, sep=';')
    return buffer.getvalue().encode('utf-8-sig')


def _find_column(columns: list[Any], candidates: tuple[str, ...]) -> Any | None:
    normalized_columns = [(_normalize(column), column) for column in columns]
    normalized_candidates = [_normalize(candidate) for candidate in candidates]
    for wanted in normalized_candidates:
        for normalized, original in normalized_columns:
            if normalized == wanted:
                return original
    for wanted in normalized_candidates:
        for normalized, original in normalized_columns:
            if wanted and wanted in normalized:
                return original
    return None


def _field_quality(value: Any, column: Any | None) -> dict[str, Any]:
    if column is None:
        return {'column': '', 'filled': 0, 'empty': 0, 'sample_values': []}
    try:
        series = value[column]
        text_values = [str(item).strip() for item in series.tolist()]
    except Exception:
        return {'column': str(column), 'filled': 0, 'empty': 0, 'sample_values': []}
    filled_values = [item for item in text_values if item and item.lower() not in {'nan', 'none', 'null'}]
    return {
        'column': str(column),
        'filled': len(filled_values),
        'empty': max(0, len(text_values) - len(filled_values)),
        'sample_values': filled_values[:8],
    }


def build_quality_report(dataframes: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for key, value in dataframes:
        try:
            columns = list(value.columns)
            shape = tuple(value.shape)
        except Exception:
            continue
        fields = {
            field: _field_quality(value, _find_column(columns, candidates))
            for field, candidates in QUALITY_CANDIDATES.items()
        }
        report.append(
            {
                'state_key': key,
                'shape': shape,
                'columns_total': len(columns),
                'columns': [str(column) for column in columns[:120]],
                'quality_fields': fields,
            }
        )
    return report


def _quality_report_csv_bytes(report: list[dict[str, Any]]) -> bytes:
    buffer = StringIO()
    fieldnames = ['state_key', 'shape', 'field', 'column', 'filled', 'empty', 'sample_values']
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    for item in report:
        for field, quality in dict(item.get('quality_fields') or {}).items():
            writer.writerow(
                {
                    'state_key': item.get('state_key', ''),
                    'shape': item.get('shape', ''),
                    'field': field,
                    'column': quality.get('column', ''),
                    'filled': quality.get('filled', 0),
                    'empty': quality.get('empty', 0),
                    'sample_values': ' | '.join(map(str, quality.get('sample_values') or [])),
                }
            )
    return buffer.getvalue().encode('utf-8-sig')


def build_support_diagnostic_zip() -> bytes:
    logs = collect_debug_logs()
    audit_events = get_audit_events()
    dataframes = collect_dataframes()
    quality_report = build_quality_report(dataframes)
    inventory = inventory_payload()
    generated_at = datetime.now().isoformat(timespec='seconds')
    dataframe_index: list[dict[str, Any]] = []

    buffer = BytesIO()
    with ZipFile(buffer, mode='w', compression=ZIP_DEFLATED) as zip_file:
        for key, dataframe in dataframes:
            filename = f'dataframes/{_safe_name(key)}_sample.csv'
            try:
                zip_file.writestr(filename, _dataframe_sample_csv_bytes(dataframe))
                shape = tuple(dataframe.shape)
                columns = [str(column) for column in list(dataframe.columns)[:120]]
                dataframe_index.append({'state_key': key, 'sample_file': filename, 'shape': shape, 'columns': columns})
            except Exception as exc:
                dataframe_index.append({'state_key': key, 'error': str(exc)[:300]})

        manifest = {
            'generated_at': generated_at,
            'audit_session_id': get_audit_session_id(),
            'counts': {
                'technical_logs': len(logs),
                'audit_events_raw': len(audit_events),
                'session_state_keys': len(st.session_state.keys()),
                'diagnostic_dataframes': len(dataframes),
                'diagnostic_dataframe_samples': sum(1 for item in dataframe_index if item.get('sample_file')),
                'system_inventory_total': int(inventory.get('summary', {}).get('total_subsystems') or 0),
            },
            'system_inventory_summary': inventory_summary(),
            'note': 'BLINGFIX: diagnostico com logs reais, amostras das bases principais e qualidade de marca/categoria/preco/imagem/SKU/GTIN.',
            'responsible_file': 'bling_app_zero/core/support_diagnostic_runtime.py',
        }

        zip_file.writestr('bling_debug.log', _logs_to_text(logs).encode('utf-8'))
        zip_file.writestr('bling_debug.json', _json_bytes(logs))
        zip_file.writestr('bling_audit_trail.jsonl', audit_download_payload())
        zip_file.writestr('bling_dataframe_quality_report.json', _json_bytes(quality_report))
        zip_file.writestr('bling_dataframe_quality_report.csv', _quality_report_csv_bytes(quality_report))
        zip_file.writestr('bling_dataframe_samples_index.json', _json_bytes(dataframe_index))
        zip_file.writestr('bling_system_inventory.json', _json_bytes(inventory))
        zip_file.writestr('bling_system_inventory.md', inventory_markdown().encode('utf-8'))
        zip_file.writestr('manifest.json', _json_bytes(manifest))
    return buffer.getvalue()


__all__ = [
    'build_quality_report',
    'build_support_diagnostic_zip',
    'collect_dataframes',
    'collect_debug_logs',
]
