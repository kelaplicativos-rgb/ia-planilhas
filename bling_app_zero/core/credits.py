from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

CREDITS_ENABLED_KEY = 'mapeiaai_credits_enabled'
CREDITS_BALANCE_KEY = 'mapeiaai_credits_balance'
CREDITS_HISTORY_KEY = 'mapeiaai_credits_history'
CREDITS_USED_SIGNATURES_KEY = 'mapeiaai_credits_used_signatures'
COST_PER_MAPPED_SHEET = 1
PRICE_PER_CREDIT_BRL = 1.0
RESPONSIBLE_FILE = 'bling_app_zero/core/credits.py'


@dataclass(frozen=True)
class CreditCheck:
    enabled: bool
    allowed: bool
    balance: int
    cost: int
    message: str


def credits_enabled() -> bool:
    """Camada preparada para produção, desligada por padrão.

    Enquanto não houver login, checkout e persistência em banco, os créditos ficam
    em modo demonstrativo/sessão para não bloquear uso real por engano.
    """
    return bool(st.session_state.get(CREDITS_ENABLED_KEY, False))


def get_credit_balance() -> int:
    try:
        return int(st.session_state.get(CREDITS_BALANCE_KEY, 0) or 0)
    except Exception:
        return 0


def set_credit_balance(value: int) -> None:
    st.session_state[CREDITS_BALANCE_KEY] = max(0, int(value or 0))


def add_demo_credits(amount: int) -> None:
    amount = max(0, int(amount or 0))
    if amount <= 0:
        return
    set_credit_balance(get_credit_balance() + amount)
    _history().append({'type': 'add_demo_credits', 'amount': amount, 'balance': get_credit_balance()})
    add_audit_event(
        'credits_added_demo',
        area='CREDITS',
        details={'amount': amount, 'balance': get_credit_balance(), 'responsible_file': RESPONSIBLE_FILE},
    )


def _history() -> list[dict]:
    history = st.session_state.get(CREDITS_HISTORY_KEY)
    if not isinstance(history, list):
        history = []
        st.session_state[CREDITS_HISTORY_KEY] = history
    return history


def _used_signatures() -> set[str]:
    signatures = st.session_state.get(CREDITS_USED_SIGNATURES_KEY)
    if not isinstance(signatures, set):
        signatures = set(signatures or []) if isinstance(signatures, (list, tuple)) else set()
        st.session_state[CREDITS_USED_SIGNATURES_KEY] = signatures
    return signatures


def mapping_already_charged(signature: str) -> bool:
    return str(signature or '') in _used_signatures()


def check_mapping_credit(signature: str) -> CreditCheck:
    if not credits_enabled():
        return CreditCheck(False, True, get_credit_balance(), 0, 'Créditos desativados nesta instalação.')
    if mapping_already_charged(signature):
        return CreditCheck(True, True, get_credit_balance(), 0, 'Esta planilha mapeada já teve crédito consumido nesta sessão.')
    balance = get_credit_balance()
    cost = COST_PER_MAPPED_SHEET
    if balance >= cost:
        return CreditCheck(True, True, balance, cost, f'Custo: {cost} crédito por planilha mapeada.')
    return CreditCheck(True, False, balance, cost, 'Créditos insuficientes para confirmar esta planilha mapeada.')


def consume_mapping_credit(signature: str, *, operation: str) -> bool:
    check = check_mapping_credit(signature)
    if not check.enabled:
        return True
    if not check.allowed:
        return False
    if check.cost <= 0 or mapping_already_charged(signature):
        return True
    set_credit_balance(get_credit_balance() - check.cost)
    _used_signatures().add(str(signature or ''))
    event = {
        'type': 'consume_mapping_credit',
        'operation': operation,
        'signature': str(signature or ''),
        'cost': check.cost,
        'balance': get_credit_balance(),
    }
    _history().append(event)
    add_audit_event(
        'mapping_credit_consumed',
        area='CREDITS',
        details={**event, 'responsible_file': RESPONSIBLE_FILE},
    )
    return True


__all__ = [
    'COST_PER_MAPPED_SHEET',
    'CREDITS_BALANCE_KEY',
    'CREDITS_ENABLED_KEY',
    'PRICE_PER_CREDIT_BRL',
    'add_demo_credits',
    'check_mapping_credit',
    'consume_mapping_credit',
    'credits_enabled',
    'get_credit_balance',
    'mapping_already_charged',
    'set_credit_balance',
]
