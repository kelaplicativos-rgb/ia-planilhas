from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender import DirectSendResult
from bling_app_zero.core.bling_direct_sender_smart import _column_map, _headers, _payload_variants, _resolve_product_id, _url
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.core.bling_v3_product_client import BlingV3ProductClient
from bling_app_zero.core.product_persistence_check import IMPORTANT_PRODUCT_FIELDS, missing_product_fields, product_persistence_flags

RESPONSIBLE_FILE = 'bling_app_zero/core/verified_api_sender.py'


def _emit(callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if callback:
        try:
            callback(payload)
        except Exception:
            pass


def _essential(payload: dict[str, Any]) -> dict[str, Any]:
    keys = ('nome', 'codigo', 'preco', 'descricaoCurta', 'descricaoComplementar', 'marca', 'unidade', 'tipo', 'situacao', 'formato', 'gtin', 'tributacao', 'categoria', 'pesoLiquido', 'pesoBruto', 'dimensoes', 'volumes', 'itensPorCaixa')
    return {key: payload[key] for key in keys if payload.get(key) not in (None, '', {}, [])}


def send_verified_products(df: pd.DataFrame, *, limit: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return DirectSendResult(0, 0, 0, len(df) if isinstance(df, pd.DataFrame) else 0, ('Bling nao conectado.',), tuple())
    if not isinstance(df, pd.DataFrame) or df.empty:
        return DirectSendResult(0, 0, 0, 0, tuple(), tuple())

    rows = df.fillna('').head(limit) if limit else df.fillna('')
    mapping = _column_map(rows.columns)
    client = BlingV3ProductClient(token=token, url_builder=_url, headers_builder=_headers, timeout=18)
    total = len(rows)
    sent = failed = skipped = 0
    errors: list[str] = []
    add_audit_event('verified_api_sender_started', area='BLING_ENVIO', status='OK', details={'total': total, 'mode': 'one_product_verify_before_next', 'responsible_file': RESPONSIBLE_FILE})

    for pos, (index, row) in enumerate(rows.iterrows(), start=1):
        line = int(index) + 1 if isinstance(index, int) else pos
        variants = _payload_variants(token, row, mapping)
        if not variants:
            skipped += 1
            errors.append(f'Linha {line}: payload nao montado.')
            continue

        _emit(progress_callback, {'stage': f'Verificando produto {pos}/{total}', 'processed': pos - 1, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': (pos - 1) / max(total, 1)})
        _label, payload, meta = variants[0]
        candidates = [meta.get('code'), meta.get('gtin'), meta.get('raw_code')]
        product_id = _resolve_product_id(token, candidates)
        attempts: list[dict[str, Any]] = []
        saved: dict[str, Any] = {}

        if product_id:
            result = client.update_product(str(product_id), payload)
            attempts.extend(dict(item) for item in result.attempts)
            saved = dict(result.persisted or {})
        else:
            created_id, create_attempts = client.create_product(payload)
            product_id = str(created_id or '')
            attempts.extend(dict(item) for item in create_attempts)
            saved = client.get_product(product_id) if product_id else {}

        missing = missing_product_fields(saved)
        if missing and product_id:
            retry = _essential(payload)
            status, _data, preview = client.request('PATCH', f'/produtos/{product_id}', retry)
            attempts.append({'method': 'PATCH', 'label': 'verified_retry_required_fields', 'status': status, 'payload_keys': sorted(retry.keys()), 'missing_before_retry': missing, 'response_preview': preview})
            if int(status) < 400:
                saved = client.get_product(product_id)
            missing = missing_product_fields(saved)

        flags = product_persistence_flags(saved)
        missing_important = missing_product_fields(saved, IMPORTANT_PRODUCT_FIELDS)
        add_audit_event('verified_api_product_checkpoint', area='BLING_ENVIO', status='OK' if not missing else 'ERRO', details={'line': line, 'product_id': product_id, 'persisted_flags': flags, 'missing_required': missing, 'missing_important': missing_important, 'image_pending': not flags.get('imagens'), 'next_product_allowed': not bool(missing), 'attempts': attempts[-6:], 'responsible_file': RESPONSIBLE_FILE})

        if missing:
            failed += 1
            if len(errors) < 8:
                errors.append(f'Linha {line}: produto nao aprovado. Faltando {", ".join(missing)}.')
            add_audit_event('verified_api_sender_finished_early', area='BLING_ENVIO', status='PARCIAL', details={'line': line, 'product_id': product_id, 'missing_fields': missing, 'sent': sent, 'failed': failed, 'responsible_file': RESPONSIBLE_FILE})
            return DirectSendResult(pos, sent, failed, skipped, tuple(errors), tuple())
        else:
            sent += 1

        _emit(progress_callback, {'stage': 'Produto aprovado; seguindo para o proximo' if not missing else 'Produto reprovado; seguindo com erro registrado', 'processed': pos, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': pos / max(total, 1)})

    add_audit_event('verified_api_sender_finished', area='BLING_ENVIO', status='OK' if failed == 0 else 'PARCIAL', details={'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(total, sent, failed, skipped, tuple(errors), tuple())


__all__ = ['send_verified_products']
