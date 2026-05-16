from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bling_app_zero.core.business_config import CREDIT_PACKAGES
from bling_app_zero.production.production_config import get_production_config
from bling_app_zero.production.user_context import CurrentUser, get_current_user


@dataclass(frozen=True)
class CheckoutRequest:
    provider: str
    package_label: str
    credits: int
    amount_brl: float
    user_id: str
    user_email: str


@dataclass(frozen=True)
class CheckoutResult:
    ok: bool
    message: str
    checkout_url: str = ''
    provider: str = ''
    payload: dict[str, Any] | None = None


def package_by_label(label: str) -> dict[str, Any] | None:
    wanted = str(label or '').strip().lower()
    for package in CREDIT_PACKAGES:
        if str(package.get('label') or '').strip().lower() == wanted:
            return dict(package)
    return None


def build_checkout_request(package_label: str, user: CurrentUser | None = None) -> CheckoutRequest | None:
    current = user or get_current_user()
    package = package_by_label(package_label)
    if not package or not current.authenticated:
        return None
    config = get_production_config()
    return CheckoutRequest(
        provider=config.payment_provider,
        package_label=str(package['label']),
        credits=int(package['credits']),
        amount_brl=float(package['price_brl']),
        user_id=current.id,
        user_email=current.email,
    )


def create_checkout(package_label: str, user: CurrentUser | None = None) -> CheckoutResult:
    """Contrato de checkout.

    Produção real: criar preferência/checkout no Mercado Pago ou Stripe,
    salvar payment pending no banco e devolver checkout_url.
    Esta função não libera crédito; crédito deve entrar somente via webhook.
    """
    request = build_checkout_request(package_label, user=user)
    if request is None:
        return CheckoutResult(False, 'Faça login e escolha um pacote válido para comprar créditos.')
    return CheckoutResult(
        ok=False,
        message='Checkout real ainda não conectado. Próximo passo: integrar Mercado Pago/Stripe e webhook.',
        provider=request.provider,
        payload={
            'package_label': request.package_label,
            'credits': request.credits,
            'amount_brl': request.amount_brl,
            'user_id': request.user_id,
            'user_email': request.user_email,
        },
    )


def handle_payment_webhook(provider: str, payload: dict[str, Any], signature: str = '') -> CheckoutResult:
    """Contrato de webhook.

    Produção real: validar assinatura, buscar pagamento no provedor,
    confirmar status aprovado, gravar payment e creditar wallet no banco.
    """
    if not provider or not isinstance(payload, dict):
        return CheckoutResult(False, 'Webhook inválido.', provider=str(provider or ''))
    return CheckoutResult(
        ok=False,
        message='Webhook recebido, mas integração real ainda não conectada.',
        provider=str(provider),
        payload={'signature_present': bool(signature), 'payload_keys': sorted(payload.keys())[:20]},
    )


__all__ = [
    'CheckoutRequest',
    'CheckoutResult',
    'build_checkout_request',
    'create_checkout',
    'handle_payment_webhook',
    'package_by_label',
]
