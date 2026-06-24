from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.api_operation_lock import lock_api_operation, resolve_api_operation
from bling_app_zero.core.flow_spine import FlowSpinePlan, build_flow_spine_plan, is_api_destination
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, OP_UNIVERSAL, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/flow_spine_output.py'
CONCRETE_API_OPERATIONS = {OP_CADASTRO, OP_ESTOQUE, OP_ATUALIZACAO_PRECO}

_OPERATION_STATE_KEYS = (
    'api_operation',
    'bling_api_operation',
    'home_bling_api_operation_choice',
    'bling_connected_api_operation',
    'flow_spine_sender_operation',
    'flow_spine_operation_resolved_for_api',
    'flow_spine_api_batch_operation',
    'direct_bling_operation_choice',
    'direct_bling_operation_applied',
    'final_download_operation',
    'df_final_download_operation',
    'df_final_preview_operation',
    'operacao_final',
    'tipo_operacao_final',
    'home_detected_operation',
    'home_slim_flow_operation',
    'site_capture_operation',
)
_SITE_HINT_KEYS = (
    'site_capture_scan_goal',
    'scan_goal',
    'site_capture_goal',
    'blingsmartscan_goal',
    'home_slim_flow_origin',
    'origem_final',
)
_DATAFRAME_STATE_KEYS = (
    'final_download_df_snapshot',
    'df_final_download',
    'df_final_preview',
    'df_final',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha_atualizacao_preco',
    'df_origem_site_como_planilha',
    'df_origem_site',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_atualizacao_preco',
    'df_site_bruto',
    'cadastro_wizard_df_origem',
    'df_origem_cadastro',
    'df_origem_estoque',
)


def _state_value(key: str) -> Any:
    try:
        return st.session_state.get(key)
    except Exception:
        return None


def _state_text(key: str) -> str:
    value = _state_value(key)
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip().lower()
    return str(value or '').strip().lower()


def _normalized_column_names(df: Any) -> list[str]:
    try:
        columns_obj = getattr(df, 'columns', [])
        columns = list(columns_obj)
    except Exception:
        return []
    normalized: list[str] = []
    replacements = {
        'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a',
        'é': 'e', 'ê': 'e', 'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ç': 'c',
    }
    for column in columns:
        text = str(column or '').strip().lower()
        for old, new in replacements.items():
            text = text.replace(old, new)
        normalized.append(' '.join(text.replace('-', ' ').replace('_', ' ').replace('/', ' ').split()))
    return normalized


def _has_any(columns: list[str], terms: tuple[str, ...]) -> bool:
    return any(any(term in column for term in terms) for column in columns)


def _operation_from_dataframe(df: Any) -> str:
    try:
        if df is None or bool(getattr(df, 'empty', False)):
            return ''
    except Exception:
        return ''

    columns = _normalized_column_names(df)
    if not columns:
        return ''

    has_name = _has_any(columns, ('nome', 'descricao', 'produto', 'titulo'))
    has_price = _has_any(columns, ('preco', 'valor', 'unitario', 'venda'))
    has_image = _has_any(columns, ('imagem', 'imagens', 'foto'))
    has_category = _has_any(columns, ('categoria', 'departamento'))
    has_qty = _has_any(columns, ('quantidade', 'qtd', 'saldo', 'estoque', 'balanco'))
    has_deposit = _has_any(columns, ('deposito', 'deposito id'))
    has_identifier = _has_any(columns, ('codigo', 'sku', 'gtin', 'ean', 'id bling', 'id produto'))
    has_price_channel = _has_any(columns, ('canal', 'loja', 'marketplace', 'id loja', 'produto loja', 'vinculo loja', 'preco destino', 'preco promocional'))

    stock_like_only = has_qty and has_identifier and not (has_name or has_price or has_image or has_category)
    price_multistore_like = has_price and has_identifier and has_price_channel and not has_qty
    price_like_only = has_price and has_identifier and not (has_qty or has_image or has_category)
    cadastro_like = has_name or has_image or has_category or (has_price and not stock_like_only and not price_multistore_like)

    if stock_like_only or (has_qty and has_deposit and not cadastro_like):
        return OP_ESTOQUE
    if price_multistore_like or price_like_only:
        return OP_ATUALIZACAO_PRECO
    if cadastro_like:
        return OP_CADASTRO
    return ''


def _explicit_operation_hint_from_state_keys() -> str:
    ops: list[str] = []
    for key in _OPERATION_STATE_KEYS:
        op = normalize_operation(_state_text(key), default=OP_UNIVERSAL)
        if op in CONCRETE_API_OPERATIONS:
            ops.append(op)
    # Preço e estoque são operações mais específicas; não deixe um cadastro antigo
    # de outro rerun sobrescrever atualização de preços multiloja ou estoque.
    for preferred in (OP_ATUALIZACAO_PRECO, OP_ESTOQUE, OP_CADASTRO):
        if preferred in ops:
            return preferred
    return ''


def _session_concrete_operation_hint() -> str:
    locked = resolve_api_operation()
    if locked in CONCRETE_API_OPERATIONS:
        return locked

    joined_hints = ' '.join(_state_text(key) for key in (*_OPERATION_STATE_KEYS, *_SITE_HINT_KEYS))
    if any(term in joined_hints for term in ('atualizacao_preco', 'atualizacao preco', 'atualizacao de preco', 'precos', 'preços', 'price', 'multiloja', 'multi loja', 'marketplace')):
        return OP_ATUALIZACAO_PRECO
    if any(term in joined_hints for term in ('estoque', 'saldo', 'stock')):
        return OP_ESTOQUE

    explicit = _explicit_operation_hint_from_state_keys()
    if explicit in CONCRETE_API_OPERATIONS:
        return explicit

    if any(term in joined_hints for term in ('cadastro', 'produto', 'produtos', 'catalogo', 'catalog')):
        return OP_CADASTRO

    for key in _DATAFRAME_STATE_KEYS:
        op = _operation_from_dataframe(_state_value(key))
        if op in CONCRETE_API_OPERATIONS:
            return op

    origin = _state_text('home_slim_flow_origin') or _state_text('origem_final') or _state_text('site_capture_raw_urls')
    unified_send = bool(_state_value('home_bling_connected_same_flow_api_send'))
    if unified_send and ('site' in origin or origin.startswith('http')):
        return OP_CADASTRO

    return ''


def output_plan() -> FlowSpinePlan:
    return build_flow_spine_plan()


def output_is_api() -> bool:
    try:
        return is_api_destination(output_plan())
    except Exception:
        return False


def preview_title() -> str:
    try:
        plan = output_plan()
        return f'Prévia final · {plan.final_title}'
    except Exception:
        return 'Prévia final'


def preview_caption() -> str:
    try:
        plan = output_plan()
        if is_api_destination(plan):
            return 'Confira a base revisada antes de enviar ao Bling. A saída final usará exatamente esta versão.'
        return plan.final_caption
    except Exception:
        return 'Confira se o arquivo final segue o modelo de destino anexado no início.'


def output_operation() -> str:
    try:
        plan = output_plan()
        op = normalize_operation(plan.operation or OP_UNIVERSAL, default=OP_UNIVERSAL)
        if is_api_destination(plan):
            hinted = _session_concrete_operation_hint()
            if hinted in CONCRETE_API_OPERATIONS:
                lock_api_operation(hinted, source=RESPONSIBLE_FILE, force=True)
                return hinted
        return op
    except Exception:
        hinted = _session_concrete_operation_hint()
        if hinted in CONCRETE_API_OPERATIONS:
            lock_api_operation(hinted, source=RESPONSIBLE_FILE, force=True)
            return hinted
        return OP_UNIVERSAL


def output_diagnostics() -> dict[str, object]:
    try:
        plan = output_plan()
        data = plan.to_dict()
        data['resolved_operation_for_api'] = output_operation()
        data['operation_resolution_source'] = RESPONSIBLE_FILE
        return data
    except Exception:
        return {'responsible_file': RESPONSIBLE_FILE, 'status': 'legacy_fallback'}


__all__ = ['output_diagnostics', 'output_is_api', 'output_operation', 'output_plan', 'preview_caption', 'preview_title']
