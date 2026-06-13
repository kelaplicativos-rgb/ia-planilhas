from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/core/operation_contract_runtime.py'
INSTALL_KEY = 'operation_contract_runtime_patch_installed_v1'


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return ' '.join(text.replace('-', '_').replace('/', '_').split())


def runtime_normalize_operation(value: object, *, default: str = 'universal') -> str:
    raw = str(value or '').strip().lower()
    text = _norm(raw)
    if raw in {'cadastro', 'estoque', 'atualizacao_preco', 'universal'}:
        return raw
    if text in {'cadastro', 'estoque', 'atualizacao_preco', 'universal'}:
        return text
    if 'estoque' in text or 'saldo' in text or 'stock' in text:
        return 'estoque'
    if 'preco' in text or 'price' in text:
        return 'atualizacao_preco'
    if 'cadastro' in text or 'produto' in text:
        return 'cadastro'
    return default if default in {'cadastro', 'estoque', 'atualizacao_preco', 'universal'} else 'universal'


def runtime_operation_label(operation: object) -> str:
    return {
        'cadastro': 'Cadastro de produtos',
        'estoque': 'Atualização de estoque',
        'atualizacao_preco': 'Atualização de preços',
        'universal': 'Automação inteligente',
    }.get(runtime_normalize_operation(operation), 'Automação inteligente')


def runtime_operation_badge(operation: object) -> str:
    return {
        'cadastro': 'Cadastro',
        'estoque': 'Estoque',
        'atualizacao_preco': 'Preços',
        'universal': 'Automação',
    }.get(runtime_normalize_operation(operation), 'Automação')


def runtime_is_price_update_operation(operation: object) -> bool:
    return runtime_normalize_operation(operation) == 'atualizacao_preco'


def install_operation_contract_runtime_patch() -> None:
    if st.session_state.get(INSTALL_KEY):
        return
    try:
        from bling_app_zero.core import operation_contract
        operation_contract.normalize_operation = runtime_normalize_operation
        operation_contract.operation_label = runtime_operation_label
        operation_contract.operation_badge = runtime_operation_badge
        operation_contract.is_price_update_operation = runtime_is_price_update_operation
        st.session_state[INSTALL_KEY] = True
        add_audit_event('operation_contract_runtime_patch_installed', area='APP', status='OK', details={'responsible_file': RESPONSIBLE_FILE})
    except Exception as exc:
        add_audit_event('operation_contract_runtime_patch_failed', area='APP', status='ERRO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_operation_contract_runtime_patch', 'runtime_normalize_operation']
