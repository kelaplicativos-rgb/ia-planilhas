from __future__ import annotations

from dataclasses import dataclass

from bling_app_zero.core.credits import check_mapping_credit, consume_mapping_credit, get_credit_balance
from bling_app_zero.production.production_config import production_mode_enabled
from bling_app_zero.production.user_context import CurrentUser, get_current_user


@dataclass(frozen=True)
class PersistentCreditResult:
    ok: bool
    message: str
    balance: int
    production: bool


def get_user_credit_balance(user: CurrentUser | None = None) -> int:
    """Retorna saldo persistente quando houver banco; por enquanto usa fallback seguro de sessão."""
    _ = user or get_current_user()
    return get_credit_balance()


def can_consume_mapping_credit(mapping_signature: str, user: CurrentUser | None = None) -> PersistentCreditResult:
    current = user or get_current_user()
    if production_mode_enabled() and not current.authenticated:
        return PersistentCreditResult(False, 'Faça login para usar créditos em produção.', 0, True)
    check = check_mapping_credit(mapping_signature)
    return PersistentCreditResult(check.allowed, check.message, check.balance, production_mode_enabled())


def consume_user_mapping_credit(mapping_signature: str, *, operation: str, user: CurrentUser | None = None) -> PersistentCreditResult:
    current = user or get_current_user()
    if production_mode_enabled() and not current.authenticated:
        return PersistentCreditResult(False, 'Faça login para confirmar esta planilha mapeada.', 0, True)
    ok = consume_mapping_credit(mapping_signature, operation=operation)
    balance = get_user_credit_balance(current)
    message = 'Crédito consumido.' if ok else 'Créditos insuficientes.'
    return PersistentCreditResult(ok, message, balance, production_mode_enabled())


__all__ = [
    'PersistentCreditResult',
    'can_consume_mapping_credit',
    'consume_user_mapping_credit',
    'get_user_credit_balance',
]
